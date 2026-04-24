import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def analyze_smile_task(self, analysis_pk, schema_name):
    """Run full smile analysis pipeline in background."""
    from django.db import connection

    from .models import SmileAnalysis

    connection.set_schema(schema_name)

    try:
        analysis = SmileAnalysis.objects.select_related("photo").get(pk=analysis_pk)
        analysis.status = SmileAnalysis.Status.PROCESSING
        analysis.save(update_fields=["status"])

        from .services import run_full_analysis
        run_full_analysis(analysis)

        logger.info("Smile analysis %s completed", analysis_pk)
    except SmileAnalysis.DoesNotExist:
        logger.error("SmileAnalysis %s not found", analysis_pk)
    except ValueError as exc:
        # Detection errors (no face found, bad image, etc.)
        logger.warning("Smile analysis %s failed: %s", analysis_pk, exc)
        SmileAnalysis.objects.filter(pk=analysis_pk).update(
            status=SmileAnalysis.Status.FAILED,
            error_message=str(exc),
        )
    except Exception as exc:
        logger.exception("Smile analysis %s error", analysis_pk)
        SmileAnalysis.objects.filter(pk=analysis_pk).update(
            status=SmileAnalysis.Status.FAILED,
            error_message=str(exc),
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=15)
def regenerate_cutout_task(self, analysis_pk, schema_name):
    """Re-generate images after manual contour/guidelines edit."""
    from django.db import connection

    from .models import SmileAnalysis

    connection.set_schema(schema_name)

    try:
        analysis = SmileAnalysis.objects.select_related("photo").get(pk=analysis_pk)

        from .services import regenerate_cutout
        regenerate_cutout(analysis)

        logger.info("Cutout regenerated for %s", analysis_pk)
    except SmileAnalysis.DoesNotExist:
        logger.error("SmileAnalysis %s not found", analysis_pk)
    except Exception as exc:
        logger.exception("Cutout regeneration failed for %s", analysis_pk)
        raise self.retry(exc=exc)
