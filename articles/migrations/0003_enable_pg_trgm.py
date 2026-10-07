from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0002_article_is_published"),
    ]

    operations = [
        TrigramExtension(),
    ]