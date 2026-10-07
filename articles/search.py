from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.contrib.postgres.search import TrigramWordSimilarity
from django.db.models import F, Q
from django.db.models.functions import Greatest
DEFAULT_MODE = "contains"


def search_contains(qs, q):
    """Har lafz AND, fields OR, icontains (purana behaviour, bilkul wahi)."""
    for word in q.split():
        qs = qs.filter(
            Q(title__icontains=word)
            | Q(subtitle__icontains=word)
            | Q(description__icontains=word)
            | Q(author__username__icontains=word)
        )
    return qs

def search_fulltext(qs, q):
    """PostgreSQL full-text: stemming + stop words + rank (title sab se zyada weight)."""
    if not q.strip():
        return qs
    vector = (
        SearchVector("title", weight="A")
        + SearchVector("subtitle", weight="B")
        + SearchVector("description", weight="C")
        + SearchVector("author__username", weight="B")
    )
    query = SearchQuery(q, search_type="websearch")
    return (
        qs.annotate(rank=SearchRank(vector, query))
        .filter(rank__gt=0)
        .order_by("-rank", "-created_at")
    )
FUZZY_THRESHOLD = 0.25


def search_fuzzy(qs, q):
    """Typo tolerant: title/subtitle/author par trigram word similarity."""
    q = q.strip()
    if not q:
        return qs
    qs = qs.annotate(
        sim=Greatest(
            TrigramWordSimilarity(q, "title"),
            TrigramWordSimilarity(q, "subtitle"),
            TrigramWordSimilarity(q, "author__username"),
        )
    )
    return qs.filter(sim__gte=FUZZY_THRESHOLD).order_by("-sim", "-created_at")
SEARCH_MODES = {
    "contains": search_contains,
    "fulltext": search_fulltext,
    "fuzzy": search_fuzzy,
}