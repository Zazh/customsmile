from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import StlScan


@login_required
def viewer(request, scan_pk):
    scan = get_object_or_404(StlScan, pk=scan_pk)
    files = scan.files.all()
    return render(request, "stl/viewer.html", {
        "scan": scan,
        "files": files,
    })


@login_required
def compare(request, scan_pk, other_scan_pk):
    scan = get_object_or_404(StlScan, pk=scan_pk)
    other_scan = get_object_or_404(StlScan, pk=other_scan_pk, patient=scan.patient)
    return render(request, "stl/compare.html", {
        "scan": scan,
        "other_scan": other_scan,
        "files": scan.files.all(),
        "other_files": other_scan.files.all(),
    })
