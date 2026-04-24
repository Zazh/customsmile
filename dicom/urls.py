from django.urls import path

from . import api, views

app_name = "dicom"

urlpatterns = [
    # HTML views
    path("<uuid:study_pk>/viewer/", views.viewer, name="viewer"),
    # JSON API
    path("upload/start/", api.upload_start, name="upload-start"),
    path("upload/chunk/<uuid:upload_id>/", api.upload_chunk, name="upload-chunk"),
    path("upload/status/<uuid:upload_id>/", api.upload_status, name="upload-status"),
]
