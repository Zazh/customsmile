import json
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import StlAnnotation, StlFile, StlScan, StlSegmentation


def api_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Требуется авторизация"}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


@api_login_required
def annotation_list(request, scan_pk):
    """GET — список аннотаций для снимка."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    scan = get_object_or_404(StlScan, pk=scan_pk)
    data = list(scan.annotations.values("id", "x", "y", "z", "text", "created_at"))
    for item in data:
        item["id"] = str(item["id"])
        item["created_at"] = item["created_at"].isoformat()
    return JsonResponse({"annotations": data})


@api_login_required
def annotation_create(request, scan_pk):
    """POST — создать аннотацию."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    scan = get_object_or_404(StlScan, pk=scan_pk)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    text = body.get("text", "").strip()
    if not text:
        return JsonResponse({"error": "Текст обязателен"}, status=400)

    try:
        x = float(body["x"])
        y = float(body["y"])
        z = float(body["z"])
    except (KeyError, ValueError, TypeError):
        return JsonResponse({"error": "Координаты x, y, z обязательны"}, status=400)

    annotation = StlAnnotation.objects.create(
        scan=scan, x=x, y=y, z=z, text=text, created_by=request.user,
    )
    return JsonResponse({
        "id": str(annotation.pk),
        "x": annotation.x,
        "y": annotation.y,
        "z": annotation.z,
        "text": annotation.text,
        "created_at": annotation.created_at.isoformat(),
    }, status=201)


@api_login_required
def annotation_delete(request, annotation_pk):
    """DELETE — удалить аннотацию."""
    if request.method != "DELETE":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    annotation = get_object_or_404(StlAnnotation, pk=annotation_pk)
    annotation.delete()
    return JsonResponse({"ok": True})


@api_login_required
def patient_scans(request, scan_pk):
    """GET — список сканов того же пациента (для сравнения)."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    scan = get_object_or_404(StlScan, pk=scan_pk)
    scans = (
        StlScan.objects
        .filter(patient=scan.patient)
        .exclude(pk=scan.pk)
        .values("id", "description", "uploaded_at")
    )
    data = []
    for s in scans:
        s["id"] = str(s["id"])
        s["uploaded_at"] = s["uploaded_at"].isoformat()
        data.append(s)
    return JsonResponse({"scans": data})


@api_login_required
def segmentation_get(request, file_pk):
    """GET — загрузить сегментацию для STL файла."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    stl_file = get_object_or_404(StlFile, pk=file_pk)
    seg = stl_file.segmentations.first()
    if not seg:
        return JsonResponse({"segmentation": None})
    return JsonResponse({
        "segmentation": {
            "id": str(seg.pk),
            "source": seg.source,
            "labels": seg.labels,
            "updated_at": seg.updated_at.isoformat(),
        }
    })


@api_login_required
def segmentation_save(request, file_pk):
    """POST — сохранить сегментацию для STL файла."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    stl_file = get_object_or_404(StlFile, pk=file_pk)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    labels = body.get("labels")
    if not isinstance(labels, dict):
        return JsonResponse({"error": "labels must be a dict"}, status=400)

    seg, _created = StlSegmentation.objects.update_or_create(
        stl_file=stl_file,
        defaults={
            "labels": labels,
            "source": StlSegmentation.Source.MANUAL,
            "created_by": request.user,
        },
    )
    return JsonResponse({
        "id": str(seg.pk),
        "updated_at": seg.updated_at.isoformat(),
    }, status=200)


@api_login_required
def segmentation_auto(request, file_pk):
    """POST — запустить автосегментацию через MeshSegNet."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    stl_file = get_object_or_404(StlFile, pk=file_pk)

    from django.db import connection

    from .tasks import segment_stl_auto_task

    schema_name = connection.schema_name
    task = segment_stl_auto_task.delay(str(stl_file.pk), schema_name)
    return JsonResponse({"task_id": task.id, "status": "started"}, status=202)


@api_login_required
def scan_files(request, scan_pk):
    """GET — список файлов снимка (для загрузки при сравнении)."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    scan = get_object_or_404(StlScan, pk=scan_pk)
    data = [
        {"id": str(f.id), "name": f.name, "category": f.category, "url": f.file.url}
        for f in scan.files.all()
    ]
    return JsonResponse({"files": data})
