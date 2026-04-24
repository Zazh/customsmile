"""
Smile analysis pipeline orchestration.

Full pipeline:
  1. detect_face_landmarks()  → landmarks JSON
  2. extract_smile_contour()  → teeth_contour + lip_contour
  3. compute_guidelines()     → guideline lines
  4. draw overlays            → contour_image, guidelines_image
  5. create_smile_cutout()    → cutout_image (teeth only), masked_image
"""

import io
import logging

import cv2
from django.core.files.base import ContentFile

from .ml.contour import draw_contour_on_image, extract_smile_contour
from .ml.cutout import create_smile_cutout
from .ml.detector import detect_face_landmarks
from .ml.guidelines import compute_guidelines, draw_guidelines_on_image

logger = logging.getLogger(__name__)


def run_full_analysis(analysis):
    """
    Run the complete smile analysis pipeline.

    Args:
        analysis: SmileAnalysis instance (with photo attached)

    Updates the analysis instance in-place and saves to DB.
    """
    image_path = analysis.photo.image.path

    # Stage 1: detect landmarks
    logger.info("Stage 1: detecting landmarks for analysis %s", analysis.pk)
    landmarks = detect_face_landmarks(image_path)
    analysis.landmarks = landmarks

    # Load image once for all drawing operations
    image = cv2.imread(image_path)
    h, w = image.shape[:2]

    # Stage 2: extract contours
    logger.info("Stage 2: extracting smile contour")
    teeth_contour, lip_contour = extract_smile_contour(landmarks, image=image)
    analysis.teeth_contour = teeth_contour
    analysis.lip_contour = lip_contour

    # Draw contour overlay
    contour_img = draw_contour_on_image(image, teeth_contour, lip_contour)
    analysis.contour_image.save(
        f"{analysis.pk}_contour.png",
        _encode_png(contour_img),
        save=False,
    )

    # Stage 3: compute guidelines
    logger.info("Stage 3: computing guidelines")
    guidelines = compute_guidelines(landmarks, (h, w))
    analysis.guidelines = guidelines

    # Draw guidelines overlay (on top of contour image)
    guidelines_img = draw_guidelines_on_image(contour_img, guidelines)
    analysis.guidelines_image.save(
        f"{analysis.pk}_guidelines.png",
        _encode_png(guidelines_img),
        save=False,
    )

    # Stage 4: cutout — вырезка по контуру зубов (не губ)
    logger.info("Stage 4: creating cutout by teeth contour")
    cutout_rgba, masked_rgba = create_smile_cutout(image, teeth_contour)
    analysis.cutout_image.save(
        f"{analysis.pk}_cutout.png",
        _encode_png(cutout_rgba),
        save=False,
    )
    analysis.masked_image.save(
        f"{analysis.pk}_masked.png",
        _encode_png(masked_rgba),
        save=False,
    )

    analysis.status = analysis.Status.DONE
    analysis.save()
    logger.info("Analysis %s complete", analysis.pk)


def regenerate_cutout(analysis):
    """
    Re-generate contour overlay, guidelines overlay, and cutout images
    after manual contour or guidelines edits.
    """
    image_path = analysis.photo.image.path
    image = cv2.imread(image_path)

    teeth_contour = analysis.teeth_contour
    lip_contour = analysis.lip_contour
    guidelines = analysis.guidelines

    # Redraw contour overlay
    contour_img = draw_contour_on_image(image, teeth_contour, lip_contour)
    analysis.contour_image.save(
        f"{analysis.pk}_contour.png",
        _encode_png(contour_img),
        save=False,
    )

    # Redraw guidelines overlay
    if guidelines:
        guidelines_img = draw_guidelines_on_image(contour_img, guidelines)
        analysis.guidelines_image.save(
            f"{analysis.pk}_guidelines.png",
            _encode_png(guidelines_img),
            save=False,
        )

    # Вырезка по контуру зубов
    cutout_rgba, masked_rgba = create_smile_cutout(image, teeth_contour)
    analysis.cutout_image.save(
        f"{analysis.pk}_cutout.png",
        _encode_png(cutout_rgba),
        save=False,
    )
    analysis.masked_image.save(
        f"{analysis.pk}_masked.png",
        _encode_png(masked_rgba),
        save=False,
    )

    analysis.save()
    logger.info("Regenerated cutout for analysis %s", analysis.pk)


def _encode_png(image_array) -> ContentFile:
    """Encode numpy array as PNG and return a Django ContentFile."""
    success, buffer = cv2.imencode(".png", image_array)
    if not success:
        raise RuntimeError("Failed to encode image as PNG")
    return ContentFile(io.BytesIO(buffer.tobytes()).read())
