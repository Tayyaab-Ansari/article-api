from django.conf import settings
from django.db import models, transaction
from django.db.models import F
class Article(models.Model):
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="articles",
        null=True,
        blank=True,
    )               
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    position = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
             ordering = ["position", "-created_at"]

    def __str__(self):
        return self.title
    def apply_revert_status(self):
        if settings.REVERT_ARTICLES_STATUS:
            self.is_published = not self.is_published
    def place_at_top(self):
        with transaction.atomic():
            Article.objects.filter(is_published=True, position__isnull=False).exclude(
                pk=self.pk
            ).update(position=F("position") + 1)
            self.position = 1

    def close_gap(self):
        if self.position is not None:
            Article.objects.filter(
                is_published=True, position__gt=self.position
            ).update(position=F("position") - 1)
            self.position = None
    def move_to(self, new_pos):
        old_pos = self.position
        if new_pos == old_pos:
            return
        with transaction.atomic():
            published = Article.objects.filter(is_published=True)
            if new_pos > old_pos:
                published.filter(
                    position__gt=old_pos, position__lte=new_pos
                ).update(position=F("position") - 1)
            else:
                published.filter(
                    position__gte=new_pos, position__lt=old_pos
                ).update(position=F("position") + 1)
            Article.objects.filter(pk=self.pk).update(position=new_pos)