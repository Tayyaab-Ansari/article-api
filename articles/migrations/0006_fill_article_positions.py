from django.db import migrations


def fill_positions(apps, schema_editor):
    Article = apps.get_model("articles", "Article")
    published = Article.objects.filter(is_published=True).order_by("-created_at")
    for number, article in enumerate(published, start=1):
        article.position = number
        article.save(update_fields=["position"])


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0005_article_position"),
    ]

    operations = [
        migrations.RunPython(fill_positions, migrations.RunPython.noop),
    ]