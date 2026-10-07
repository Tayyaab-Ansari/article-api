from django.db.models import Q

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


SEARCH_MODES = {
    "contains": search_contains,
}