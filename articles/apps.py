from django.apps import AppConfig


class ArticlesConfig(AppConfig):
    name = 'articles'

    def ready(self):
        from . import signals  # noqa: F401