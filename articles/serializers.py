from rest_framework import serializers

from .models import Article


class ArticleSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source="author.username")

    class Meta:
        model = Article
        fields = ["id", "title", "subtitle", "description", "author", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]