from django.urls import path

from . import api, views

app_name = "smile"

urlpatterns = [
    # HTML views
    path("<uuid:analysis_pk>/editor/", views.editor, name="editor"),
    # JSON API
    path("api/upload/", api.photo_upload, name="photo-upload"),
    path("api/analysis/<uuid:analysis_pk>/", api.analysis_detail, name="analysis-detail"),
    path("api/analysis/<uuid:analysis_pk>/contour/", api.contour_update, name="contour-update"),
    path("api/analysis/<uuid:analysis_pk>/guidelines/", api.guidelines_update, name="guidelines-update"),
    path("api/analysis/<uuid:analysis_pk>/regenerate/", api.regenerate, name="regenerate"),
    path("api/patient/<uuid:patient_pk>/photos/", api.patient_photos, name="patient-photos"),
]
