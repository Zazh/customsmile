import json
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import SmileAnalysis, SmilePhoto


def api_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Требуется авторизация"}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


@api_login_required
def photo_upload(request):
    """POST — загрузить фото и запустить анализ улыбки."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    image = request.FILES.get("image")
    if not image:
        return JsonResponse({"error": "Файл image обязателен"}, status=400)

    patient_id = request.POST.get("patient_id")
    if not patient_id:
        return JsonResponse({"error": "patient_id обязателен"}, status=400)

    from patient.models import Patient
    patient = get_object_or_404(Patient, pk=patient_id)

    photo = SmilePhoto.objects.create(
        patient=patient,
        image=image,
        description=request.POST.get("description", ""),
        uploaded_by=request.user,
    )

    analysis = SmileAnalysis.objects.create(photo=photo)

    # Launch async analysis
    from django.db import connection
    from .tasks import analyze_smile_task
    schema_name = connection.schema_name
    task = analyze_smile_task.delay(str(analysis.pk), schema_name)

    return JsonResponse({
        "photo_id": str(photo.pk),
        "analysis_id": str(analysis.pk),
        "task_id": task.id,
        "status": analysis.status,
    }, status=201)


@api_login_required
def analysis_detail(request, analysis_pk):
    """GET — получить статус и результаты анализа."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    analysis = get_object_or_404(
        SmileAnalysis.objects.select_related("photo", "photo__patient"),
        pk=analysis_pk,
    )

    data = {
        "id": str(analysis.pk),
        "status": analysis.status,
        "error_message": analysis.error_message,
        "photo_url": analysis.photo.image.url,
        "teeth_contour": analysis.teeth_contour,
        "lip_contour": analysis.lip_contour,
        "guidelines": analysis.guidelines,
        "contour_image_url": analysis.contour_image.url if analysis.contour_image else None,
        "guidelines_image_url": analysis.guidelines_image.url if analysis.guidelines_image else None,
        "cutout_image_url": analysis.cutout_image.url if analysis.cutout_image else None,
        "masked_image_url": analysis.masked_image.url if analysis.masked_image else None,
        "updated_at": analysis.updated_at.isoformat(),
    }
    return JsonResponse(data)


@api_login_required
def contour_update(request, analysis_pk):
    """PUT — сохранить отредактированный контур (из интерактивного редактора)."""
    if request.method != "PUT":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    analysis = get_object_or_404(SmileAnalysis, pk=analysis_pk)
    if analysis.status != SmileAnalysis.Status.DONE:
        return JsonResponse({"error": "Анализ ещё не завершён"}, status=400)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    teeth = body.get("teeth_contour")
    lip = body.get("lip_contour")

    if teeth is not None:
        if not isinstance(teeth, list):
            return JsonResponse({"error": "teeth_contour must be a list"}, status=400)
        analysis.teeth_contour = teeth

    if lip is not None:
        if not isinstance(lip, list):
            return JsonResponse({"error": "lip_contour must be a list"}, status=400)
        analysis.lip_contour = lip

    analysis.save(update_fields=["teeth_contour", "lip_contour", "updated_at"])

    return JsonResponse({
        "id": str(analysis.pk),
        "updated_at": analysis.updated_at.isoformat(),
    })


@api_login_required
def guidelines_update(request, analysis_pk):
    """PUT — сохранить отредактированные направляющие."""
    if request.method != "PUT":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    analysis = get_object_or_404(SmileAnalysis, pk=analysis_pk)
    if analysis.status != SmileAnalysis.Status.DONE:
        return JsonResponse({"error": "Анализ ещё не завершён"}, status=400)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    guidelines = body.get("guidelines")
    if not isinstance(guidelines, dict):
        return JsonResponse({"error": "guidelines must be a dict"}, status=400)

    analysis.guidelines = guidelines
    analysis.save(update_fields=["guidelines", "updated_at"])

    return JsonResponse({
        "id": str(analysis.pk),
        "updated_at": analysis.updated_at.isoformat(),
    })


@api_login_required
def regenerate(request, analysis_pk):
    """POST — пересоздать изображения после ручных правок контура/направляющих."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    analysis = get_object_or_404(SmileAnalysis, pk=analysis_pk)
    if analysis.status != SmileAnalysis.Status.DONE:
        return JsonResponse({"error": "Анализ ещё не завершён"}, status=400)

    from django.db import connection
    from .tasks import regenerate_cutout_task
    schema_name = connection.schema_name
    task = regenerate_cutout_task.delay(str(analysis.pk), schema_name)

    return JsonResponse({"task_id": task.id, "status": "started"}, status=202)


@api_login_required
def patient_photos(request, patient_pk):
    """GET — все фото улыбок пациента с последним анализом."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    photos = SmilePhoto.objects.filter(patient_id=patient_pk).order_by("-uploaded_at")
    data = []
    for photo in photos:
        analysis = photo.analyses.first()
        data.append({
            "photo_id": str(photo.pk),
            "image_url": photo.image.url,
            "description": photo.description,
            "uploaded_at": photo.uploaded_at.isoformat(),
            "analysis": {
                "id": str(analysis.pk),
                "status": analysis.status,
            } if analysis else None,
        })

    return JsonResponse({"photos": data})
