from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action

from .models import Article
from .permissions import IsAuthorOrReadOnly
from .serializers import ArticleSerializer
from rest_framework.response import Response
from .search import DEFAULT_MODE, SEARCH_MODES
from django.conf import settings
from django.db import transaction
from django.db.models import F
from rest_framework import serializers as drf_serializers

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
    def get_permissions(self):
        if self.action in ("list", "search"):
            return [permissions.AllowAny()]
        return super().get_permissions()
    
    def get_queryset(self):
        qs = Article.objects.select_related("author")
        if getattr(self, "swagger_fake_view", False):
            return qs.none()
        user = self.request.user
        if user.is_authenticated:
            return qs.filter(Q(is_published=True) | Q(author=user))
        return qs.filter(is_published=True)

    def perform_create(self, serializer):
        if "is_published" in self.request.data:
            serializer.save(author=self.request.user)
        else:
            serializer.save(
                author=self.request.user,
                is_published=settings.AUTO_PUBLISH_ARTICLES,
            )
    def perform_update(self, serializer):
        if "is_published" in self.request.data:
            serializer.instance._user_set_published = True
        serializer.save()

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
    @extend_schema(
        request=inline_serializer(
            name="MoveArticle",
            fields={"position": drf_serializers.IntegerField(min_value=1)},
        ),
        responses=ArticleSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="move",
        permission_classes=[permissions.IsAuthenticated],
    )
    def move(self, request, pk=None):
        new_pos = request.data.get("position")
        try:
            new_pos = int(new_pos)
        except (TypeError, ValueError):
            return Response({"position": ["A whole number is required."]}, status=400)
        with transaction.atomic():
            published = Article.objects.select_for_update().filter(is_published=True)
            total = published.count()
            article = self.get_object()
            article = Article.objects.select_for_update().get(pk=article.pk)

            if not article.is_published or article.position is None:
                return Response(
                    {"detail": "Draft articles cannot be moved."}, status=400
                )
            if new_pos < 1 or new_pos > total:
                return Response(
                    {"position": [f"Must be between 1 and {total}."]}, status=400
                )

            article.move_to(new_pos)

        article.refresh_from_db()
        return Response(self.get_serializer(article).data)