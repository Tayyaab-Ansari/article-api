from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Article


@receiver(pre_save, sender=Article)
def revert_status_on_update(sender, instance, **kwargs):
    # Naya article: flip nahi
    if instance.pk is None:
        return
    # View ne bataya ke user ne is_published khud bheja: uski value rakho
    if getattr(instance, "_user_set_published", False):
        return
    # Warna stored value par flag ke hisaab se flip
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    instance.is_published = old.is_published
    instance.apply_revert_status()