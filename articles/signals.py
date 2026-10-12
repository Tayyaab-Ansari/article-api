from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import Article

@receiver(pre_save, sender=Article)
def handle_article_save(sender, instance, **kwargs):
    old = None
    if instance.pk is not None:
        old = sender.objects.filter(pk=instance.pk).first()
    was_published = old.is_published if old is not None else False
    if instance.is_published and not was_published:
        instance.place_at_top()
    elif not instance.is_published and was_published:
        instance.position = old.position
        instance.close_gap()


@receiver(pre_delete, sender=Article)
def close_gap_on_delete(sender, instance, **kwargs):
    if instance.is_published:
        instance.close_gap()