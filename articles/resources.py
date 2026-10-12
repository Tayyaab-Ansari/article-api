from import_export.fields import Field
from import_export.resources import ModelResource

from .models import Article

EXPORT_COLUMNS = ("title", "subtitle", "description", "status", "author")


class ArticleExportResource(ModelResource):
    status = Field(column_name="status")
    author = Field(column_name="author", attribute="author__username")

    class Meta:
        model = Article
        fields = EXPORT_COLUMNS
        export_order = EXPORT_COLUMNS

    def get_queryset(self):
        return Article.objects.filter(is_published=True).select_related("author")

    def dehydrate_status(self, article):
        return "published" if article.is_published else "draft"