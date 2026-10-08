from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action

from .models import Article
from .permissions import IsAuthorOrReadOnly
from .serializers import ArticleSerializer
from rest_framework.response import Response
from .search import DEFAULT_MODE, SEARCH_MODES
from django.conf import settings

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
        if "is_published" in self.request.data:
            serializer.save(author=self.request.user)
        else:
            serializer.save(
                author=self.request.user,
                is_published=settings.AUTO_PUBLISH_ARTICLES,
            )
    def perform_destroy(self, instance):
        instance.author = None
        instance.save(update_fields=["author"])
        instance.delete()
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="q",
                type=str,
                required=False,
                description="Search words (title, subtitle, text or author username)",
            ),
            OpenApiParameter(
                name="mode",
                type=str,
                required=False,
                enum=list(SEARCH_MODES),
                default=DEFAULT_MODE,
                description="Search mode. Empty or missing means 'contains'.",
            ),
        ],
        responses=ArticleSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        q = request.query_params.get("q", "").strip()
        mode = request.query_params.get("mode") or DEFAULT_MODE

        search_fn = SEARCH_MODES.get(mode)
        if search_fn is None:
            return Response(
                {"mode": [f"Invalid mode '{mode}'. Choose one of: {', '.join(SEARCH_MODES)}."]},
                status=400,
            )

        queryset = search_fn(self.get_queryset(), q)  # drafts rule get_queryset() se aati hai

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
    