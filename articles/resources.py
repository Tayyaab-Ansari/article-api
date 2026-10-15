from import_export.fields import Field
from import_export.resources import ModelResource
from import_export.widgets import Widget

from .models import Article

EXPORT_COLUMNS = ("uuid","title", "subtitle", "description", "status", "author")


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


class StatusWidget(Widget):
    """Excel ke 'status' column ko True ya False (published ya draft) banata hai."""

    PUBLISHED_WORDS = {"published", "publish"}
    DRAFT_WORDS = {"draft", ""}

    def clean(self, value, row=None, **kwargs):
        text = "" if value is None else str(value).strip().lower()
        if text in self.PUBLISHED_WORDS:
            return True
        if text in self.DRAFT_WORDS:
            return False
        raise ValueError("Status must be 'published' or 'draft'.")


class ArticleImportResource(ModelResource):
    is_published = Field(
        column_name="status", attribute="is_published", widget=StatusWidget()
    )

    class Meta:
        model = Article
        fields = ("title", "subtitle", "description", "is_published")
        import_id_fields = ("title",)
        clean_model_instances = True

    def __init__(self, author=None, **kwargs):
        super().__init__(**kwargs)
        self.author = author

    def get_queryset(self):
        return Article.objects.filter(author=self.author)

    def before_save_instance(self, instance, row, **kwargs):
        instance.author = self.author
        # Excel ka khali cell None ban kar aata hai, lekin subtitle null nahi ho sakta
        if instance.subtitle is None:
            instance.subtitle = ""