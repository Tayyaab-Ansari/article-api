from rest_framework import serializers

from .models import Article


class ArticleSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source="author.username")

    class Meta:
        model = Article
        fields = [
            "id", "title", "subtitle", "description", "author",
            "is_published", "position",
            "ai_summary", "summary_status", "summary_requested_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "author", "position",
            "ai_summary", "summary_status", "summary_requested_at",
            "created_at", "updated_at",
        ]
class SummaryEditSerializer(serializers.Serializer):
    ai_summary = serializers.CharField(max_length=2000)