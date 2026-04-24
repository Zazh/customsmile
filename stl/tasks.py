import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def extract_stl_files_task(self, scan_pk, schema_name):
    """Извлечь STL файлы из ZIP-архива в фоне."""
    from django.db import connection

    from .models import StlScan
    from .services import extract_stl_files

    connection.set_schema(schema_name)

    try:
        scan = StlScan.objects.get(pk=scan_pk)
        extract_stl_files(scan)
        count = scan.files.count()
        logger.info("STL %s: извлечено %d файлов", scan_pk, count)
    except StlScan.DoesNotExist:
        logger.error("STL %s: скан не найден", scan_pk)
    except Exception as exc:
        logger.exception("STL %s: ошибка распаковки", scan_pk)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def segment_stl_auto_task(self, file_pk, schema_name):
    """Автосегментация STL файла с помощью MeshSegNet."""
    from django.db import connection

    from .models import StlFile, StlSegmentation

    connection.set_schema(schema_name)

    try:
        stl_file = StlFile.objects.get(pk=file_pk)
        file_path = stl_file.file.path
        logger.info("Auto-segmentation started: %s (%s)", stl_file.name, file_pk)

        # Determine jaw type from file category
        jaw = "upper" if stl_file.category == "upper" else "lower"
        logger.info("Detected jaw: %s (category=%s)", jaw, stl_file.category)

        from .ml.inference import segment_mesh
        labels = segment_mesh(file_path, jaw=jaw)

        if not labels:
            logger.warning("Auto-segmentation produced no labels for %s", file_pk)
            return

        StlSegmentation.objects.update_or_create(
            stl_file=stl_file,
            defaults={
                "labels": labels,
                "source": StlSegmentation.Source.AUTO,
            },
        )
        face_count = sum(len(v) for v in labels.values())
        logger.info(
            "Auto-segmentation complete: %s — %d labels, %d faces",
            file_pk, len(labels), face_count,
        )

    except StlFile.DoesNotExist:
        logger.error("STL file %s not found", file_pk)
    except FileNotFoundError as exc:
        logger.error("Model weights not found: %s", exc)
    except Exception as exc:
        logger.exception("Auto-segmentation failed for %s", file_pk)
        raise self.retry(exc=exc)
