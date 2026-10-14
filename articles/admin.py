from django.contrib import admin

from .models import Article,ImportJob


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "author", "created_at")
    search_fields = ("title", "subtitle", "description")
@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "filename",
        "new_count",
        "updated_count",
        "skipped_count",
        "created_at",
        "finished_at",
    )
    list_filter = ("status",)
    list_select_related = ("user",)
    search_fields = ("filename", "user__username")
    show_facets = admin.ShowFacets.ALWAYS
    exclude = ("rows",)

    def get_queryset(self, request):
        return super().get_queryset(request).defer("rows")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False