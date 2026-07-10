"""
tools/topics.py

Groups a batch of newly-crawled articles into topic clusters (TF-IDF +
k-means, same as before) — but labels each cluster from the per-article
keywords already extracted during summarization (tools/summarize.py),
instead of matching against a fixed vocabulary. Clustering decides the
*grouping*; the pooled keywords of each cluster's members decide the
*name*. This replaces the old fixed 6-category keyword-heuristic
labeling, which tended to over-label everything "AI" once a cluster had
even a couple of AI-adjacent articles pulling in unrelated ones.

Keyword extraction itself (tools/summarize.py) stays fully independent
of this — it runs once per article with no awareness of clustering or
other articles. This module only consumes those already-assigned
keywords as input for cluster naming.
"""

from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from sklearn.cluster import KMeans
except ImportError:
    # Some environments (restrictive DLL/extension policies, minimal
    # containers) can't load sklearn's compiled clustering extensions
    # even though the pure-Python TF-IDF path works fine. Degrade to
    # keyword-only labeling rather than failing the whole crawl step.
    KMeans = None

MAX_TOPICS = 10


def _label_from_keywords(keyword_lists: list[list[str]]) -> str:
    """Pool a cluster's members' keywords and name it after the top 1-2."""
    counter = Counter()
    for keywords in keyword_lists:
        counter.update(keywords)
    if not counter:
        return "Other"
    top_terms = [term for term, _ in counter.most_common(2)]
    return " / ".join(term.title() for term in top_terms)


def cluster_topics(articles: list[dict]) -> None:
    """Mutates each article dict in place, setting article['topic']."""
    if not articles:
        return

    if len(articles) < 3 or KMeans is None:
        for article in articles:
            article["topic"] = _label_from_keywords([article.get("keywords") or []])
        return

    texts = [f"{a.get('title', '')} {a.get('summary') or ''}" for a in articles]

    vectorizer = TfidfVectorizer(stop_words="english", max_features=2000)
    matrix = vectorizer.fit_transform(texts)

    num_clusters = max(2, min(MAX_TOPICS, len(articles) // 2))
    kmeans = KMeans(n_clusters=num_clusters, n_init=10, random_state=42)
    cluster_ids = kmeans.fit_predict(matrix)

    cluster_keywords: dict[int, list[list[str]]] = {}
    for cluster_id, article in zip(cluster_ids, articles):
        cluster_keywords.setdefault(cluster_id, []).append(article.get("keywords") or [])

    cluster_labels = {
        cluster_id: _label_from_keywords(keyword_lists)
        for cluster_id, keyword_lists in cluster_keywords.items()
    }

    for article, cluster_id in zip(articles, cluster_ids):
        article["topic"] = cluster_labels[cluster_id]
