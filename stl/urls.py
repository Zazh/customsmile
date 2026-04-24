from django.urls import path

from . import api, views

app_name = "stl"

urlpatterns = [
    # HTML views
    path("<uuid:scan_pk>/viewer/", views.viewer, name="viewer"),
    path("<uuid:scan_pk>/compare/<uuid:other_scan_pk>/", views.compare, name="compare"),
    # JSON API
    path("api/<uuid:scan_pk>/annotations/", api.annotation_list, name="annotation-list"),
    path("api/<uuid:scan_pk>/annotations/create/", api.annotation_create, name="annotation-create"),
    path("api/annotations/<uuid:annotation_pk>/delete/", api.annotation_delete, name="annotation-delete"),
    path("api/<uuid:scan_pk>/patient-scans/", api.patient_scans, name="patient-scans"),
    path("api/<uuid:scan_pk>/files/", api.scan_files, name="scan-files"),
    path("api/files/<uuid:file_pk>/segmentation/", api.segmentation_get, name="segmentation-get"),
    path("api/files/<uuid:file_pk>/segmentation/save/", api.segmentation_save, name="segmentation-save"),
    path("api/files/<uuid:file_pk>/segmentation/auto/", api.segmentation_auto, name="segmentation-auto"),
]
