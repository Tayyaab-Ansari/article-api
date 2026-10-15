from celery import shared_task
from datetime import timedelta
import httpx
from django.conf import settings
from .models import Article, ImportJob
from django.utils import timezone
from .importing import run_import
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

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
def count_summaries():
    published = Article.objects.filter(is_published=True)
    total = published.count()
    with_summary = (
        published.exclude(ai_summary__isnull=True).exclude(ai_summary="").count()
    )
    without_summary = total - with_summary
    logger.info(
        "Summaries: with=%s, without=%s, total published=%s",
        with_summary,
        without_summary,
        total,
    )
    return f"with={with_summary}, without={without_summary}"
@shared_task
def run_import_job(job_id):
    claimed = ImportJob.objects.filter(pk=job_id, status="queued").update(
        status="running", started_at=timezone.now()
    )
    if not claimed:
        return "skipped: job is not queued"

    job = ImportJob.objects.get(pk=job_id)
    try:
        counts = run_import(job)
    except Exception as exc:
        ImportJob.objects.filter(pk=job_id).update(
            status="failed",
            error_message=str(exc)[:2000],
            finished_at=timezone.now(),
        )
        logger.info("Import job %s failed: %s", job_id, exc)
        return f"failed: {exc}"

    ImportJob.objects.filter(pk=job_id).update(
        status="done",
        new_count=counts["new"],
        updated_count=counts["updated"],
        skipped_count=counts["skipped"],
        finished_at=timezone.now(),
    )
    logger.info("Import job %s done: %s", job_id, counts)
    return f"done: {counts}"
PREVIEW_MAX_AGE_MINUTES = 10


@shared_task
def process_waiting_imports():
    queued = deleted = 0

    if settings.AUTO_START_CLEAN_IMPORTS:
        clean_ids = list(
            ImportJob.objects.filter(
                status="previewed", ready_count__gt=0
            ).values_list("pk", flat=True)
        )
        for job_id in clean_ids:
            job = ImportJob.objects.get(pk=job_id)
            if job.queue():
                queued += 1

    cutoff = timezone.now() - timedelta(minutes=PREVIEW_MAX_AGE_MINUTES)
    deleted, _ = ImportJob.objects.filter(
        status="previewed", created_at__lt=cutoff
    ).delete()

    logger.info("Waiting imports: queued=%s, deleted=%s", queued, deleted)
    return f"queued={queued}, deleted={deleted}"