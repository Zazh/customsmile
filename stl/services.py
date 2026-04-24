import os
import zipfile
from datetime import date

from django.conf import settings
from django.core.files.base import ContentFile


def detect_category(filename):
    """Detect jaw category from STL filename."""
    from .models import StlFile

    name_lower = filename.lower()
    if "upper" in name_lower:
        return StlFile.Category.UPPER
    if "lower" in name_lower:
        return StlFile.Category.LOWER
    if "buccal" in name_lower:
        return StlFile.Category.BUCCAL
    return StlFile.Category.OTHER


def extract_stl_files(scan):
    """Extract .stl files from uploaded ZIP archive and create StlFile objects."""
    from .models import StlFile

    archive_path = scan.archive.path
    if not zipfile.is_zipfile(archive_path):
        return

    today = date.today()
    rel_dir = os.path.join("stl", "files", today.strftime("%Y"), today.strftime("%m"), today.strftime("%d"))
    dest_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
    os.makedirs(dest_dir, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as zf:
        for entry in zf.namelist():
            if not entry.lower().endswith(".stl"):
                continue
            basename = os.path.basename(entry)
            if not basename:
                continue

            data = zf.read(entry)
            category = detect_category(basename)
            stl_file = StlFile(scan=scan, name=basename, category=category)
            stl_file.file.save(basename, ContentFile(data), save=True)
