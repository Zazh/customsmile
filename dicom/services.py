import logging
import os
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

ORTHANC_URL = getattr(settings, "ORTHANC_URL", os.environ.get("ORTHANC_URL", "http://orthanc:8042"))
ORTHANC_AUTH = (
    os.environ.get("ORTHANC_USER", "customsmile"),
    os.environ.get("ORTHANC_PASSWORD", "orthanc-secret-change-me"),
)
REQUEST_TIMEOUT = 300
MAX_ZIP_EXTRACT_SIZE = 5 * 1024 * 1024 * 1024  # 5 GB
UPLOAD_WORKERS = 8  # параллельных потоков для загрузки в Orthanc


def _upload_single_file(file_path: str) -> str | None:
    """Upload one DICOM file to Orthanc. Returns Orthanc internal study ID."""
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{ORTHANC_URL}/instances",
            data=f,
            headers={"Content-Type": "application/dicom"},
            auth=ORTHANC_AUTH,
            timeout=REQUEST_TIMEOUT,
        )
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list):
            data = data[0] if data else {}
        return data.get("ParentStudy")
    # Not a valid DICOM — skip silently (ZIPs often contain non-DICOM files)
    if resp.status_code == 400:
        return None
    logger.error("Orthanc upload failed (%s): %s", resp.status_code, resp.text[:200])
    return None


def _get_study_instance_uid(orthanc_id: str) -> str | None:
    """Get DICOM StudyInstanceUID from Orthanc internal ID."""
    resp = requests.get(
        f"{ORTHANC_URL}/studies/{orthanc_id}",
        auth=ORTHANC_AUTH,
        timeout=30,
    )
    if resp.status_code == 200:
        tags = resp.json().get("MainDicomTags", {})
        return tags.get("StudyInstanceUID")
    return None


def upload_to_orthanc(file_path: str) -> str | None:
    """Upload DICOM file or ZIP archive to Orthanc. Returns StudyInstanceUID."""
    if zipfile.is_zipfile(file_path):
        return _upload_zip(file_path)

    parent_study = _upload_single_file(file_path)
    if parent_study:
        return _get_study_instance_uid(parent_study)
    return None


def _upload_zip(zip_path: str) -> str | None:
    """Extract ZIP and upload DICOM files in parallel."""
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                total_size = sum(info.file_size for info in zf.infolist())
                if total_size > MAX_ZIP_EXTRACT_SIZE:
                    logger.error("ZIP exceeds max extract size: %d bytes", total_size)
                    return None
                for member in zf.namelist():
                    safe_path = os.path.normpath(os.path.join(tmpdir, member))
                    if not safe_path.startswith(os.path.normpath(tmpdir) + os.sep) and safe_path != os.path.normpath(tmpdir):
                        logger.error("Zip path traversal detected: %s", member)
                        return None
                zf.extractall(tmpdir)
        except NotImplementedError:
            logger.error("ZIP uses unsupported compression: %s", zip_path)
            return None

        # Collect all files
        file_paths = []
        for root, _dirs, files in os.walk(tmpdir):
            for name in files:
                file_paths.append(os.path.join(root, name))

        if not file_paths:
            return None

        logger.info("Uploading %d files from ZIP to Orthanc (%d workers)...", len(file_paths), UPLOAD_WORKERS)

        # Upload in parallel
        parent_study = None
        with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as pool:
            futures = {pool.submit(_upload_single_file, fp): fp for fp in file_paths}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    parent_study = result

        if parent_study:
            return _get_study_instance_uid(parent_study)
        return None
