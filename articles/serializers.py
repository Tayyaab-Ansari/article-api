from rest_framework import serializers

from .models import Article


class ArticleSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source="author.username")

    class Meta:
        model = Article
        fields = ["id", "title", "subtitle", "description", "author", "is_published", "position", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "position", "created_at", "updated_at"]