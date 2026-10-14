import uuid

from django.db import migrations


def fill_uuids(apps, schema_editor):
    Article = apps.get_model("articles", "Article")
    for article in Article.objects.filter(uuid__isnull=True).iterator():
        Article.objects.filter(pk=article.pk).update(uuid=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0009_article_uuid'),
    ]

    operations = [
        migrations.RunPython(fill_uuids, migrations.RunPython.noop),
    ]