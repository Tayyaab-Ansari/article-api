from rest_framework import filters, mixins, permissions, viewsets
from django.db.models import Q
from .models import Article
from .permissions import IsAuthorOrReadOnly
from .serializers import ArticleSerializer


class ArticleViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):

    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "subtitle", "description", "author__username"]
    def get_queryset(self):
        qs = Article.objects.select_related("author")
        if getattr(self, "swagger_fake_view", False):
            return qs.none()
        return qs.filter(Q(is_published=True) | Q(author=self.request.user))
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)