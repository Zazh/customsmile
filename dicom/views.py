from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import DicomStudy


@login_required
def viewer(request, study_pk):
    study = get_object_or_404(DicomStudy, pk=study_pk)
    if not study.orthanc_study_id:
        raise Http404("Исследование ещё не загружено в Orthanc")
    return render(request, "dicom/viewer.html", {
        "study": study,
        "ohif_url": settings.OHIF_URL,
    })
