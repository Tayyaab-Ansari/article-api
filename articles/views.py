from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action

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

    def get_queryset(self):
        qs = Article.objects.select_related("author")
        if getattr(self, "swagger_fake_view", False):
            return qs.none()
        return qs.filter(Q(is_published=True) | Q(author=self.request.user))

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="q",
                type=str,
                required=False,
                description="Search words (title, subtitle, text or author username)",
            )
        ],
        responses=ArticleSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        queryset = self.get_queryset()  # Option B (drafts) khud lag jata hai

        q = request.query_params.get("q", "").strip()
        for word in q.split():
            queryset = queryset.filter(
                Q(title__icontains=word)
                | Q(subtitle__icontains=word)
                | Q(description__icontains=word)
                | Q(author__username__icontains=word)
            )

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)