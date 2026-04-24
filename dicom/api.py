import json
import os
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import ChunkedUpload

ALLOWED_EXTENSIONS = {".dcm", ".zip"}
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB


def api_staff_required(view_func):
    """Like @staff_member_required but returns JSON 403 instead of HTML redirect."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse({"error": "Требуется авторизация"}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def require_post_json(view_func):
    """Like @require_POST but returns JSON 405."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method != "POST":
            return JsonResponse({"error": "Method not allowed"}, status=405)
        return view_func(request, *args, **kwargs)
    return wrapper


def require_get_json(view_func):
    """Like @require_GET but returns JSON 405."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method != "GET":
            return JsonResponse({"error": "Method not allowed"}, status=405)
        return view_func(request, *args, **kwargs)
    return wrapper


@api_staff_required
@require_post_json
def upload_start(request):
    """Начать загрузку: создать сессию, вернуть upload_id."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    filename = body.get("filename", "")
    total_size = body.get("total_size", 0)

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse(
            {"error": f"Допустимые форматы: {', '.join(ALLOWED_EXTENSIONS)}"},
            status=400,
        )

    if not total_size or total_size > MAX_FILE_SIZE:
        return JsonResponse({"error": "Недопустимый размер файла"}, status=400)

    upload = ChunkedUpload.objects.create(
        user=request.user,
        filename=filename,
        total_size=total_size,
    )

    upload_dir = Path(upload.temp_path).parent
    upload_dir.mkdir(parents=True, exist_ok=True)

    return JsonResponse({
        "upload_id": str(upload.pk),
        "offset": 0,
    })


@api_staff_required
@require_post_json
def upload_chunk(request, upload_id):
    """Принять очередной чанк и дописать в файл."""
    upload = get_object_or_404(
        ChunkedUpload, pk=upload_id, status=ChunkedUpload.Status.UPLOADING,
    )

    if upload.user_id and upload.user_id != request.user.pk:
        return JsonResponse({"error": "Forbidden"}, status=403)

    chunk = request.body
    if not chunk:
        return JsonResponse({"error": "Empty chunk"}, status=400)

    offset = upload.offset
    with open(upload.temp_path, "ab") as f:
        f.seek(offset)
        f.write(chunk)

    upload.offset = offset + len(chunk)
    if upload.offset >= upload.total_size:
        upload.status = ChunkedUpload.Status.COMPLETE
    upload.save(update_fields=["offset", "status"])

    return JsonResponse({
        "upload_id": str(upload.pk),
        "offset": upload.offset,
        "status": upload.status,
    })


@api_staff_required
@require_get_json
def upload_status(request, upload_id):
    """Вернуть текущий offset — клиент использует для resume."""
    upload = get_object_or_404(ChunkedUpload, pk=upload_id)
    return JsonResponse({
        "upload_id": str(upload.pk),
        "offset": upload.offset,
        "total_size": upload.total_size,
        "status": upload.status,
    })
