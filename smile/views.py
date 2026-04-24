from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import SmileAnalysis


@login_required
def editor(request, analysis_pk):
    analysis = get_object_or_404(
        SmileAnalysis.objects.select_related("photo", "photo__patient"),
        pk=analysis_pk,
    )
    return render(request, "smile/editor.html", {"analysis": analysis})
