from rest_framework import filters, mixins, permissions, viewsets

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
    queryset = Article.objects.select_related("author")
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "subtitle", "description", "author__username"]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)