"""
Google Drive upload helper for dry-marking PDFs.

Requires GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_DRIVE_FOLDER_ID in settings.

GOOGLE_SERVICE_ACCOUNT_JSON can be:
  - A file path to the service account JSON file, or
  - The raw JSON string of the service account credentials.

Setup steps:
  1. Create a Google Cloud project and enable the Google Drive API.
  2. Create a service account and download its JSON key.
  3. Share the target Drive folder with the service account's email
     (give it "Editor" access).
  4. Set GOOGLE_SERVICE_ACCOUNT_JSON to the JSON file path or content string.
  5. Set GOOGLE_DRIVE_FOLDER_ID to the folder ID from the Drive URL.
"""
import io
import json
import logging
import os

logger = logging.getLogger(__name__)

_SCOPES = ['https://www.googleapis.com/auth/drive.file']


def _build_service():
    """Return an authenticated Google Drive service object."""
    from django.conf import settings

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ImportError(
            'google-api-python-client and google-auth are required. '
            'Run: pip install google-api-python-client google-auth-httplib2 google-auth'
        ) from exc

    raw = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_JSON', '')
    if not raw:
        raise ValueError(
            'GOOGLE_SERVICE_ACCOUNT_JSON is not set. '
            'Provide a file path or the raw JSON string of your service account key.'
        )

    # Determine if it's a file path or inline JSON
    if raw.strip().startswith('{'):
        # Inline JSON string
        info = json.loads(raw)
    elif os.path.isfile(raw):
        with open(raw, 'r', encoding='utf-8') as f:
            info = json.load(f)
    else:
        raise ValueError(
            f'GOOGLE_SERVICE_ACCOUNT_JSON is set but is neither valid JSON nor '
            f'an existing file path: {raw!r}'
        )

    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=_SCOPES
    )
    return build('drive', 'v3', credentials=credentials, cache_discovery=False)


def upload_pdf(pdf_bytes: bytes, filename: str) -> str:
    """
    Upload *pdf_bytes* as *filename* to the configured Google Drive folder.

    Returns the Drive file ID of the newly created file.
    Raises on any error so the caller can handle gracefully.
    """
    from django.conf import settings
    from googleapiclient.http import MediaIoBaseUpload

    folder_id = getattr(settings, 'GOOGLE_DRIVE_FOLDER_ID', '')
    if not folder_id:
        raise ValueError('GOOGLE_DRIVE_FOLDER_ID is not configured in settings.')

    service = _build_service()

    file_metadata = {
        'name': filename,
        'parents': [folder_id],
    }

    media = MediaIoBaseUpload(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        resumable=False,
    )

    created = (
        service.files()
        .create(body=file_metadata, media_body=media, fields='id,name')
        .execute()
    )

    file_id = created.get('id')
    logger.info('Dry-marking PDF uploaded to Drive: %s (id=%s)', filename, file_id)
    return file_id
