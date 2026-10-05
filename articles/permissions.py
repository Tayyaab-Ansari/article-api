from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Anyone can read; only the article's author can modify or delete it."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user