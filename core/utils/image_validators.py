"""
Image validation utilities for question images.
Enforces MIME type, dimensions, file size, and EXIF stripping.
"""
import io
import uuid
import re

from django.core.exceptions import ValidationError
from django.utils.text import slugify


ALLOWED_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
}

MAX_FILE_SIZE = 2 * 1024 * 1024   # 2 MB
MIN_DIMENSION = 100                 # pixels
MAX_DIMENSION = 4000                # pixels
MAX_FILENAME_LENGTH = 100


def validate_question_image(value):
    """
    Full validation chain for a question image upload.
    Called by the model field validator.

    Checks (in order):
      1. File size <= 2 MB
      2. Real MIME type via python-magic (content sniffing, not just extension)
      3. Extension matches detected MIME type
      4. Image dimensions within allowed range (via Pillow)
      5. Strips EXIF metadata from the in-memory file before Django saves it
    """
    from PIL import Image
    import magic  # python-magic-bin on Windows

    file = value.file

    # ── 1. File size ──────────────────────────────────────────────────────────
    file.seek(0, 2)  # seek to end
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        raise ValidationError(
            f'File size must be under 2 MB (your file is {size_mb:.1f} MB).'
        )

    # ── 2. Real MIME type (content sniffing) ──────────────────────────────────
    header = file.read(2048)
    file.seek(0)
    detected_mime = magic.from_buffer(header, mime=True)

    if detected_mime not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f'Only JPEG, PNG, or WebP files are allowed. '
            f'Detected type: {detected_mime}.'
        )

    # ── 3. Extension matches MIME ─────────────────────────────────────────────
    ext_map = {
        'image/jpeg': {'.jpg', '.jpeg'},
        'image/png':  {'.png'},
        'image/webp': {'.webp'},
    }
    filename = value.name.lower()
    dot = filename.rfind('.')
    ext = filename[dot:] if dot != -1 else ''
    allowed_exts = ext_map.get(detected_mime, set())
    if ext not in allowed_exts:
        raise ValidationError(
            f'File extension "{ext}" does not match detected type {detected_mime}. '
            'Rename the file with the correct extension.'
        )

    # ── 4. Image dimensions via Pillow ────────────────────────────────────────
    try:
        img = Image.open(io.BytesIO(file.read()))
        file.seek(0)
        img.verify()  # catches truncated or corrupted images
        # Re-open after verify (verify closes the stream)
        file.seek(0)
        img = Image.open(io.BytesIO(file.read()))
        file.seek(0)
        w, h = img.size
    except Exception:
        raise ValidationError('Uploaded file is not a valid image or is corrupted.')

    if w < MIN_DIMENSION or h < MIN_DIMENSION:
        raise ValidationError(
            f'Image must be at least {MIN_DIMENSION}×{MIN_DIMENSION} pixels '
            f'(your image is {w}×{h}).'
        )
    if w > MAX_DIMENSION or h > MAX_DIMENSION:
        raise ValidationError(
            f'Image cannot exceed {MAX_DIMENSION}×{MAX_DIMENSION} pixels '
            f'(your image is {w}×{h}).'
        )

    # ── 5. Strip EXIF metadata ────────────────────────────────────────────────
    # Rebuild the image without EXIF to protect privacy (GPS, device info, etc.)
    try:
        file.seek(0)
        original = Image.open(io.BytesIO(file.read()))
        file.seek(0)

        buf = io.BytesIO()
        fmt_map = {'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WEBP'}
        fmt = fmt_map[detected_mime]

        # Convert to RGB for JPEG (remove alpha channel if present)
        if fmt == 'JPEG' and original.mode in ('RGBA', 'P'):
            original = original.convert('RGB')

        # Save without any metadata
        original.save(buf, format=fmt, optimize=True)
        buf.seek(0)

        # Replace the underlying file data in-place
        value.file = buf
        value.size = buf.getbuffer().nbytes
    except Exception:
        raise ValidationError('Failed to process image. Please try a different file.')


def sanitize_image_filename(original_name: str) -> str:
    """
    Return a safe filename: exam_question_<uuid4>.<ext>
    Strips path separators, spaces, and special characters.
    """
    dot = original_name.rfind('.')
    ext = original_name[dot:].lower() if dot != -1 else '.jpg'
    return f'exam_question_{uuid.uuid4().hex}{ext}'
