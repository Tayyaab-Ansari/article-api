from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .importing import ImportConfirmSerializer, ImportJobSerializer
from .models import ImportJob
from .tasks import run_import_job


class ImportJobViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ImportJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ImportJob.objects.none()
        return ImportJob.objects.filter(user=self.request.user)

    @extend_schema(
        request=ImportConfirmSerializer, responses={202: ImportJobSerializer}
    )
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        job = self.get_object()
        serializer = ImportConfirmSerializer(data=request.data, context={"job": job})
        serializer.is_valid(raise_exception=True)
        update_rows = serializer.validated_data["update_rows"]

        with transaction.atomic():
            claimed = ImportJob.objects.filter(pk=job.pk, status="previewed").update(
                status="queued", update_rows=update_rows
            )
            if claimed:
                transaction.on_commit(lambda: run_import_job.delay(job.pk))

        if not claimed:
            return Response(
                {"detail": "This import was already confirmed."}, status=409
            )

        job.refresh_from_db()
        return Response(ImportJobSerializer(job).data, status=202)