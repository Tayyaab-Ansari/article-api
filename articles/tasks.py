from celery import shared_task

from .models import Article
import httpx
from django.conf import settings


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
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
            json={
                "model": settings.OPENROUTER_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "Summarize the article in 2-3 clear English sentences.",
                    },
                    {"role": "user", "content": article.description[:6000]},
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if "choices" not in data:
            raise ValueError(f"OpenRouter error: {data.get('error')}")
        summary = data["choices"][0]["message"]["content"].strip()
        Article.objects.filter(pk=article_id).update(
            ai_summary=summary, summary_status="done"
        )
        return "done"
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            # Rate limit: retry se quota aur khatam hota hai, foran failed
            Article.objects.filter(pk=article_id).update(summary_status="failed")
            return "rate limited"
        if self.request.retries >= self.max_retries:
            Article.objects.filter(pk=article_id).update(summary_status="failed")
            return f"failed: {exc}"
        raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            Article.objects.filter(pk=article_id).update(summary_status="failed")
            return f"failed: {exc}"
        raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))
@shared_task
def hello(name):
    return f"Hello {name}"