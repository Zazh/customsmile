import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_to_orthanc(self, study_pk, file_path, schema_name):
    """Отправить DICOM файл в Orthanc в фоне."""
    from django.db import connection

    from .models import DicomStudy
    from .services import upload_to_orthanc

    # Переключаемся на схему тенанта
    connection.set_schema(schema_name)

    try:
        study_id = upload_to_orthanc(file_path)
        if study_id:
            DicomStudy.objects.filter(pk=study_pk).update(orthanc_study_id=study_id)
            logger.info("DICOM %s → Orthanc OK: %s", study_pk, study_id)
        else:
            logger.error("DICOM %s → Orthanc failed, retrying...", study_pk)
            raise self.retry()
    except self.MaxRetriesExceededError:
        logger.error("DICOM %s → Orthanc failed after %d retries", study_pk, self.max_retries)
    except Exception as exc:
        logger.exception("DICOM %s → Orthanc error", study_pk)
        raise self.retry(exc=exc)
