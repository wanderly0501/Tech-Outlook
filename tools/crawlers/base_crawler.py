"""
tools/crawlers/base_crawler.py

Generic, multi-threaded, breadth-first site crawler. This is the same
engine as web_crawler_verge.py, generalized so any site plugin can
reuse it: the two things that used to be hardcoded to The Verge
(the date filter and the "is this URL an article" check) are now
callables the site plugin supplies.
"""

from __future__ import annotations

import time
import queue
import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import urlopen, Request

from bs4 import BeautifulSoup


def normalize_url(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return None
        if not parsed.netloc:
            return None

        scheme = parsed.scheme.lower()
        hostname = parsed.hostname.lower()
        path = parsed.path or "/"
        if path != "/" and path.endswith("/"):
            path = path[:-1]

        return urlunparse((scheme, hostname, path, "", parsed.query, ""))
    except Exception:
        return None


def is_allowed_domain(url: str, allowed_domains: Set[str]) -> bool:
    parsed = urlparse(url)
    if parsed.hostname is None:
        return False
    hostname = parsed.hostname.lower()
    for allowed_domain in allowed_domains:
        if hostname == allowed_domain or hostname.endswith("." + allowed_domain):
            return True
    return False


def extract_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        normalized_url = normalize_url(urljoin(base_url, tag["href"]))
        if normalized_url:
            links.append(normalized_url)
    return links


class PerHostRateLimiter:
    def __init__(self, min_delay_seconds: float) -> None:
        self.min_delay_seconds = min_delay_seconds
        self.lock = threading.Lock()
        self.next_allowed_time: Dict[str, float] = {}

    def wait(self, hostname: str) -> None:
        while True:
            now = time.monotonic()
            with self.lock:
                next_time = self.next_allowed_time.get(hostname, now)
                if now >= next_time:
                    self.next_allowed_time[hostname] = now + self.min_delay_seconds
                    return
            time.sleep(max(0, next_time - now))


@dataclass
class CrawlTask:
    url: str
    depth: int
    retry_count: int = 0


@dataclass
class CrawlResult:
    url: str
    depth: int
    new_links: list[str] = field(default_factory=list)
    error: Optional[str] = None
    html_content: Optional[str] = None


class WebCrawler:
    """
    Generic breadth-first crawler with a per-host rate limiter and a
    thread pool of workers.

    `is_article_url` and `date_extractor` are optional hooks a site
    plugin uses to (a) recognize which discovered URLs are actual
    articles (as opposed to nav/listing/tag pages) and (b) read the
    publish date back out of a fetched page's HTML. When `filter_date`
    is set, both hooks must be provided: pages older than filter_date
    stop that branch of the crawl (articles are listed newest-first,
    so this is a safe way to bound the crawl to "today").
    """

    def __init__(
        self,
        start_urls: List[str],
        allowed_domains: List[str],
        num_threads: int = 8,
        max_depth: int = 2,
        min_delay_seconds: float = 0.5,
        max_retry: int = 2,
        request_timeout: float = 10.0,
        user_agent: str = "crawler/1.0",
        max_num: int = 500,
        filter_date: Optional[date] = None,
        is_article_url: Optional[Callable[[str], bool]] = None,
        date_extractor: Optional[Callable[[str], Optional[date]]] = None,
    ) -> None:
        self.start_urls = []
        for url in start_urls:
            n_url = normalize_url(url)
            if n_url:
                self.start_urls.append(n_url)
        if not self.start_urls:
            raise ValueError("no valid start urls")

        if not allowed_domains:
            raise ValueError("no allowed domains")

        if filter_date is not None and (is_article_url is None or date_extractor is None):
            raise ValueError("filter_date requires both is_article_url and date_extractor")

        self.user_agent = user_agent

        canonical_allowed_domains = set()
        for domain in allowed_domains:
            canonical_allowed_domains.add(domain)
            if domain.startswith("www."):
                canonical_allowed_domains.add(domain[4:])
            else:
                canonical_allowed_domains.add(f"www.{domain}")
        self.allowed_domains = canonical_allowed_domains

        self.max_retry = max_retry
        self.max_depth = max_depth
        self.num_threads = num_threads

        self.rate_limiter = PerHostRateLimiter(min_delay_seconds)
        self.request_timeout = request_timeout

        self.seen_lock = threading.Lock()
        self.seen: Set[str] = set()

        self.results_lock = threading.Lock()
        self.results: List[CrawlResult] = []

        self.stop_event = threading.Event()

        self.tasks: queue.Queue = queue.Queue()
        self.threads: List[threading.Thread] = []
        self.max_num = max_num
        self.filter_date = filter_date
        self.is_article_url = is_article_url
        self.date_extractor = date_extractor

    def crawl(self) -> List[CrawlResult]:
        for url in self.start_urls:
            self._schedule_if_new(url)

        for i in range(self.num_threads):
            thread = threading.Thread(target=self._worker, name=f"crawler-{i}", daemon=True)
            thread.start()
            self.threads.append(thread)

        self.tasks.join()
        self.stop()
        for _ in range(self.num_threads):
            self.tasks.put(None)
        for thread in self.threads:
            thread.join()
        return self.results

    def stop(self) -> None:
        self.stop_event.set()

    def _schedule_if_new(self, url: str, depth: int = 0, retry: int = 0) -> bool:
        with self.seen_lock:
            if len(self.seen) >= self.max_num:
                return False
            if url not in self.seen:
                self.seen.add(url)
                self.tasks.put(CrawlTask(url, depth, retry))
                return True
        return False

    def _worker(self) -> None:
        while not self.stop_event.is_set():
            task = self.tasks.get()
            if task is None:
                self.tasks.task_done()
                return
            try:
                self._process_task(task)
            finally:
                self.tasks.task_done()

    def _process_task(self, task: CrawlTask) -> None:
        try:
            result = self._fetch(task)
        except Exception as e:
            if task.retry_count < self.max_retry:
                time.sleep(2**task.retry_count)
                self.tasks.put(CrawlTask(task.url, task.depth, task.retry_count + 1))
                return
            result = CrawlResult(task.url, task.depth, new_links=[], error=str(e))

        if self.filter_date is not None:
            if result.html_content and self.is_article_url(result.url):
                article_date = self.date_extractor(result.html_content)
                if article_date and article_date >= self.filter_date:
                    with self.results_lock:
                        self.results.append(result)
                if article_date and article_date < self.filter_date:
                    return
        else:
            with self.results_lock:
                self.results.append(result)

        if result.depth >= self.max_depth:
            return

        for new_link in result.new_links:
            if is_allowed_domain(new_link, self.allowed_domains):
                self._schedule_if_new(new_link, task.depth + 1, 0)

    def _fetch(self, task: CrawlTask) -> CrawlResult:
        url = task.url
        parsed = urlparse(url)
        self.rate_limiter.wait(parsed.hostname)

        headers = {"User-Agent": self.user_agent}
        request = Request(url, headers=headers)
        with urlopen(request, timeout=self.request_timeout) as response:
            body_bytes = response.read()
            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()

        new_links = []
        html_content = None
        if content_type.startswith("text/html"):
            html_content = body_bytes.decode("utf-8", errors="replace")
            new_links = extract_links(url, html_content)

        return CrawlResult(url, task.depth, new_links, html_content=html_content)
