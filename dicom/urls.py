from django.urls import path

from . import views

app_name = "dicom"

urlpatterns = [
    path("<uuid:study_pk>/viewer/", views.viewer, name="viewer"),
]
