
from django.db.models import Count
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .importing import (
    ImportConfirmSerializer,
    ImportJobListSerializer,
    ImportJobSerializer,
)
from .models import ImportJob
from .tasks import run_import_job

STATUS_VALUES = [value for value, _label in ImportJob.STATUS_CHOICES]


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="status",
                type=str,
                required=False,
                enum=STATUS_VALUES,
                description="Only jobs with this status.",
            )
        ]
    )
)
class ImportJobViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "list":
            return ImportJobListSerializer
        return ImportJobSerializer

    def _visible_jobs(self):
        jobs = ImportJob.objects.all()
        if not self.request.user.is_staff:
            jobs = jobs.filter(user=self.request.user)
        return jobs

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ImportJob.objects.none()
        jobs = self._visible_jobs().select_related("user")
        if self.action == "list":
            jobs = jobs.defer("rows")
        return jobs

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        if self.action == "list":
            wanted = self.request.query_params.get("status")
            if wanted:
                if wanted not in STATUS_VALUES:
                    raise ValidationError(
                        {"status": [f"Choose one of: {', '.join(STATUS_VALUES)}."]}
                    )
                queryset = queryset.filter(status=wanted)
        return queryset

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        grouped = (
            self._visible_jobs().order_by().values("status").annotate(n=Count("id"))
        )
        counts = {value: 0 for value in STATUS_VALUES}
        for item in grouped:
            counts[item["status"]] = item["n"]
        return Response(
            {
                "scope": "all" if request.user.is_staff else "mine",
                "total": sum(counts.values()),
                "counts": counts,
            }
        )

    @extend_schema(
        request=ImportConfirmSerializer, responses={202: ImportJobSerializer}
    )
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        job = self.get_object()
        if job.user_id != request.user.id:
            return Response(
                {"detail": "Only the owner can confirm this import."}, status=403
            )
        serializer = ImportConfirmSerializer(data=request.data, context={"job": job})
        serializer.is_valid(raise_exception=True)
        update_rows = serializer.validated_data["update_rows"]
        if not job.queue(update_rows):
            return Response(
                {"detail": "This import was already confirmed."}, status=409
            )

        job.refresh_from_db()
        return Response(ImportJobSerializer(job).data, status=202)