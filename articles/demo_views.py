from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response

from .models import Article
from .permissions import IsAuthorOrReadOnly
from .serializers import ArticleSerializer


# A) ModelViewSet: sab 5 actions ready-made milte hain
@extend_schema(tags=["Demo"])
class ArticleModelDemoViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.select_related("author")
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


# B) GenericViewSet + mixins: sirf wo actions jo hum chahte hain
@extend_schema(tags=["Demo"])
class ArticleMixinDemoViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Article.objects.select_related("author")
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


# C) GenericViewSet khud: har action ka code hum khud likhte hain
@extend_schema(tags=["Demo"])
class ArticleManualDemoViewSet(viewsets.GenericViewSet):
    queryset = Article.objects.select_related("author")
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def retrieve(self, request, pk=None):
        article = self.get_object()
        return Response(self.get_serializer(article).data)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)