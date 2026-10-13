from collections import Counter

import tablib
from django.db import transaction
from rest_framework import serializers

from .resources import ArticleImportResource, StatusWidget
from django.core.exceptions import MultipleObjectsReturned
from .models import ImportJob

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 500
REQUIRED_COLUMNS = ("title", "subtitle", "description", "status")


class ImportFileSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, uploaded):
        if not uploaded.name.lower().endswith(".xlsx"):
            raise serializers.ValidationError("Only .xlsx files are accepted.")
        if uploaded.size > MAX_FILE_BYTES:
            raise serializers.ValidationError("File is too large (max 5 MB).")
        return uploaded


def load_dataset(uploaded):
    """Excel file ko tablib Dataset banata hai aur file ki bunyadi jaanch karta hai."""
    try:
        dataset = tablib.Dataset().load(uploaded.read(), format="xlsx")
    except Exception:
        raise serializers.ValidationError(
            {"file": ["Could not read this file. Is it a valid .xlsx?"]}
        )

    # Header ke naam chhote harf aur bina faltu space ke ("Title " bhi chale)
    dataset.headers = [
        "" if h is None else str(h).strip().lower() for h in (dataset.headers or [])
    ]

    missing = [c for c in REQUIRED_COLUMNS if c not in dataset.headers]
    if missing:
        raise serializers.ValidationError(
            {"file": ["Missing columns: " + ", ".join(missing) + "."]}
        )
    if len(dataset) == 0:
        raise serializers.ValidationError({"file": ["The file has no rows."]})
    if len(dataset) > MAX_ROWS:
        raise serializers.ValidationError(
            {"file": [f"Too many rows ({len(dataset)}). The limit is {MAX_ROWS}."]}
        )

    # Title ke aage peeche ke space hatao, taake "Mine " aur "Mine" ek hi gine jayen
    titles = ["" if t is None else str(t).strip() for t in dataset["title"]]
    del dataset["title"]
    dataset.append_col(titles, header="title")
    return dataset


def _effective_status(raw):
    """Preview mein dikhane ke liye: kya banega (published/draft), ya ghalat text jaisa hai waisa."""
    try:
        return "published" if StatusWidget().clean(raw) else "draft"
    except ValueError:
        return "" if raw is None else str(raw)


def _error_messages(row):
    messages = []
    problems = getattr(row, "validation_error", None)
    if problems is not None:
        if hasattr(problems, "message_dict"):
            for field, texts in problems.message_dict.items():
                label = "status" if field == "is_published" else field
                messages += [f"{label}: {text}" for text in texts]
        else:
            messages.append(str(problems))
    for error in row.errors:
        if isinstance(error.error, MultipleObjectsReturned):
            messages.append(
                "You have more than one article with this title, "
                "so it cannot be matched. Rename or delete the extra one first."
            )
    if row.errors and not messages:
        messages.append("Could not process this row.")
    return messages

def build_preview(dataset, author):
    # dry_run ke upar apna rollback bhi: kuch bhi ho, database mein kuch nahi rehta
    with transaction.atomic():
        result = ArticleImportResource(author=author).import_data(
            dataset, dry_run=True
        )
        transaction.set_rollback(True)

    source_rows = dataset.dict
    first_seen = {}
    rows = []
    for index, row in enumerate(result.rows):
        source = source_rows[index]
        title = source["title"]
        row_number = index + 2  # Excel mein row 1 header hai
        messages = []

        if row.import_type == "new":
            kind = "ready"
        elif row.import_type == "update":
            kind = "conflict"
        else:
            kind = "error"
            messages = _error_messages(row)

        if kind != "error":
            if title in first_seen:
                kind = "error"
                messages = [f"Duplicate title: same as row {first_seen[title]}."]
            else:
                first_seen[title] = row_number

        rows.append(
            {
                "row": row_number,
                "title": title,
                "status": _effective_status(source["status"]),
                "result": kind,
                "messages": messages,
            }
        )

    counts = Counter(r["result"] for r in rows)
    summary = {
        "total": len(rows),
        "ready": counts["ready"],
        "conflict": counts["conflict"],
        "error": counts["error"],
    }
    return {"summary": summary, "rows": rows}
def _plain(value):
    """Cell ki value JSON mein rakhne ke qabil banata hai (None ya text)."""
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def dataset_to_rows(dataset):
    """Dataset ki rows ko dictionaries ki list banata hai (database ke JSONField ke liye)."""
    rows = []
    for index, source in enumerate(dataset.dict):
        rows.append(
            {
                "row": index + 2,  # Excel mein row 1 header hai
                "title": source["title"],
                "subtitle": _plain(source["subtitle"]),
                "description": _plain(source["description"]),
                "status": _plain(source["status"]),
            }
        )
    return rows


def rows_to_dataset(rows):
    """Database mein rakhi rows se wapas Dataset banata hai (confirm ke waqt kaam aayega)."""
    dataset = tablib.Dataset(headers=list(REQUIRED_COLUMNS))
    for r in rows:
        dataset.append([r["title"], r["subtitle"], r["description"], r["status"]])
    return dataset
class ImportFailed(Exception):
    """Asal import mein koi row save nahi ho saki, is liye poora import wapas."""


def select_rows_to_import(job):
    """Confirm ke waqt dobara classify karke wo rows chunta hai jo import hongi."""
    dataset = rows_to_dataset(job.rows)
    preview = build_preview(dataset, job.user)
    wanted_updates = {int(n) for n in job.update_rows}
    by_number = {r["row"]: r for r in job.rows}

    chosen = []
    for item in preview["rows"]:
        if item["result"] == "ready":
            chosen.append(by_number[item["row"]])
        elif item["result"] == "conflict" and item["row"] in wanted_updates:
            chosen.append(by_number[item["row"]])
    return chosen


def run_import(job):
    """Chuni hui rows asal mein save karta hai, ek hi transaction mein."""
    chosen = select_rows_to_import(job)
    created = updated = 0
    if chosen:
        with transaction.atomic():
            result = ArticleImportResource(author=job.user).import_data(
                rows_to_dataset(chosen), dry_run=False
            )
            problems = [
                r for r in result.rows if r.import_type in ("error", "invalid")
            ]
            if problems or result.base_errors:
                raise ImportFailed(f"{len(problems)} row(s) could not be saved.")
            created = sum(1 for r in result.rows if r.import_type == "new")
            updated = sum(1 for r in result.rows if r.import_type == "update")
    return {
        "new": created,
        "updated": updated,
        "skipped": len(job.rows) - created - updated,
    }
class ImportJobSerializer(serializers.ModelSerializer):
    total_rows = serializers.SerializerMethodField()

    class Meta:
        model = ImportJob
        fields = (
            "id",
            "status",
            "filename",
            "total_rows",
            "new_count",
            "updated_count",
            "skipped_count",
            "error_message",
            "created_at",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields

    def get_total_rows(self, job) -> int:
        return len(job.rows)


class ImportConfirmSerializer(serializers.Serializer):
    update_rows = serializers.ListField(
        child=serializers.IntegerField(min_value=2),
        required=False,
        default=list,
    )

    def validate_update_rows(self, numbers):
        known = {r["row"] for r in self.context["job"].rows}
        unknown = sorted(set(numbers) - known)
        if unknown:
            raise serializers.ValidationError(f"Unknown row numbers: {unknown}.")
        return sorted(set(numbers))