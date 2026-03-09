import logging
import os
import tempfile
import zipfile

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

ORTHANC_URL = getattr(settings, "ORTHANC_URL", os.environ.get("ORTHANC_URL", "http://orthanc:8042"))
REQUEST_TIMEOUT = 120


def _upload_single_file(file_path: str) -> str | None:
    """Upload a single DICOM file to Orthanc. Returns DICOM StudyInstanceUID."""
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{ORTHANC_URL}/instances",
            data=f,
            headers={"Content-Type": "application/dicom"},
            timeout=REQUEST_TIMEOUT,
        )
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list):
            data = data[0] if data else {}
        parent_study = data.get("ParentStudy")
        if parent_study:
            return _get_study_instance_uid(parent_study)
    logger.error("Orthanc upload failed: %s %s", resp.status_code, resp.text)
    return None


def _get_study_instance_uid(orthanc_id: str) -> str | None:
    """Get DICOM StudyInstanceUID from Orthanc internal ID."""
    resp = requests.get(f"{ORTHANC_URL}/studies/{orthanc_id}", timeout=REQUEST_TIMEOUT)
    if resp.status_code == 200:
        tags = resp.json().get("MainDicomTags", {})
        return tags.get("StudyInstanceUID")
    return None


def upload_to_orthanc(file_path: str) -> str | None:
    """Upload DICOM file or ZIP archive to Orthanc. Returns study ID."""
    if zipfile.is_zipfile(file_path):
        return _upload_zip(file_path)
    return _upload_single_file(file_path)


def _upload_zip(zip_path: str) -> str | None:
    """Extract ZIP and upload each DICOM file inside."""
    study_id = None
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    if os.path.isabs(member) or ".." in member:
                        logger.error("Zip path traversal detected: %s", member)
                        return None
                zf.extractall(tmpdir)
        except NotImplementedError:
            logger.error("ZIP uses unsupported compression: %s", zip_path)
            return None
        for root, _dirs, files in os.walk(tmpdir):
            for name in files:
                fpath = os.path.join(root, name)
                result = _upload_single_file(fpath)
                if result:
                    study_id = result
    return study_id
