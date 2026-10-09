from celery import shared_task

from .models import Article


@shared_task(bind=True, max_retries=3)
def generate_ai_summary(self, article_id):
    try:
        article = Article.objects.get(pk=article_id)
    except Article.DoesNotExist:
        return "article missing"

    if not article.is_published:
        Article.objects.filter(pk=article_id).update(summary_status="failed")
        return "draft skipped"

    try:
        # Abhi fake summary; asli AI (OpenRouter) agle step mein
        summary = article.description[:200]
        Article.objects.filter(pk=article_id).update(
            ai_summary=summary, summary_status="done"
        )
        return "done"
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            Article.objects.filter(pk=article_id).update(summary_status="failed")
            raise
        raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))


@shared_task
def hello(name):
    return f"Hello {name}"