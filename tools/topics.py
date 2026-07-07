"""
tools/topics.py

Deterministic topic assignment: TF-IDF + k-means groups articles into
clusters, then each cluster is labeled against a fixed vocabulary
(AI, Hardware, Policy, Apps, Science, Other) by keyword overlap.
Clustering decides *grouping*, the keyword pass decides the *name* —
kept out of the LLM's hands so labels stay stable run to run.
"""

from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from sklearn.cluster import KMeans
except ImportError:
    # Some environments (restrictive DLL/extension policies, minimal
    # containers) can't load sklearn's compiled clustering extensions
    # even though the pure-Python TF-IDF path works fine. Degrade to
    # keyword-only labeling rather than failing the whole crawl step.
    KMeans = None

CATEGORIES = ["AI", "Hardware", "Policy", "Apps", "Science", "Other"]

_CATEGORY_KEYWORDS = {
    "AI": ["ai", "artificial intelligence", "machine learning", "llm", "chatbot",
           "openai", "anthropic", "claude", "gpt", "model", "neural", "agent"],
    "Hardware": ["chip", "processor", "device", "phone", "laptop", "hardware",
                 "silicon", "gadget", "camera", "battery", "smartphone", "semiconductor"],
    "Policy": ["regulation", "law", "policy", "congress", "government", "antitrust",
               "lawsuit", "senate", "ban", "court", "fcc", "ftc", "privacy", "compliance"],
    "Apps": ["app", "software", "update", "feature", "ios", "android",
             "browser", "platform", "subscription"],
    "Science": ["science", "space", "nasa", "climate", "research", "study",
                "physics", "biology", "energy", "quantum"],
}


def _label_by_keywords(text: str) -> str:
    text_lower = text.lower()
    best_category = "Other"
    best_count = 0
    for category, keywords in _CATEGORY_KEYWORDS.items():
        count = sum(text_lower.count(kw) for kw in keywords)
        if count > best_count:
            best_count = count
            best_category = category
    return best_category


def assign_topics(articles: list[dict]) -> None:
    """Mutates each article dict in place, setting article['topic']."""
    if not articles:
        return

    texts = [f"{a.get('title', '')} {a.get('summary') or ''}" for a in articles]

    if len(articles) < 3 or KMeans is None:
        for article, text in zip(articles, texts):
            article["topic"] = _label_by_keywords(text)
        return

    vectorizer = TfidfVectorizer(stop_words="english", max_features=2000)
    matrix = vectorizer.fit_transform(texts)

    num_clusters = max(2, min(7, len(articles) // 2))
    kmeans = KMeans(n_clusters=num_clusters, n_init=10, random_state=42)
    cluster_ids = kmeans.fit_predict(matrix)

    # Label each cluster once by pooling its articles' text, then apply
    # that label to every member — cheaper and more stable than labeling
    # per-article, and keeps semantically similar articles grouped together.
    cluster_text = {}
    for cluster_id, text in zip(cluster_ids, texts):
        cluster_text.setdefault(cluster_id, []).append(text)

    cluster_labels = {
        cluster_id: _label_by_keywords(" ".join(texts))
        for cluster_id, texts in cluster_text.items()
    }

    for article, cluster_id in zip(articles, cluster_ids):
        article["topic"] = cluster_labels[cluster_id]
