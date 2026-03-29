"""
Google Drive upload helper for dry-marking PDFs.

Uses OAuth 2.0 with a pre-authorised refresh token so files are uploaded
to any regular Google Drive folder (personal or university account).

Required settings / .env variables:
  GOOGLE_OAUTH_CLIENT_ID      – OAuth 2.0 client ID (Desktop App type)
  GOOGLE_OAUTH_CLIENT_SECRET  – OAuth 2.0 client secret
  GOOGLE_OAUTH_REFRESH_TOKEN  – long-lived refresh token (one-time setup)
  GOOGLE_DRIVE_FOLDER_ID      – target Drive folder ID (from URL)

One-time setup:
  1. In Google Cloud Console → APIs & Services → Credentials:
       Create an OAuth 2.0 Client ID of type "Desktop app".
       Copy the Client ID and Client Secret into .env.
  2. Enable the Google Drive API for the project.
  3. Run:  python get_drive_token.py
       Follow the browser prompt and paste the code back.
       Copy the printed refresh token into .env as GOOGLE_OAUTH_REFRESH_TOKEN.
  4. Set GOOGLE_DRIVE_FOLDER_ID to your Drive folder ID.
"""
import io
import logging

logger = logging.getLogger(__name__)


def _build_service():
    """Return an authenticated Google Drive service object (OAuth2 refresh token)."""
    from django.conf import settings

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ImportError(
            'google-api-python-client and google-auth are required. '
            'Run: pip install google-api-python-client google-auth-httplib2 google-auth'
        ) from exc

    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', '')
    refresh_token = getattr(settings, 'GOOGLE_OAUTH_REFRESH_TOKEN', '')

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError(
            'GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, and '
            'GOOGLE_OAUTH_REFRESH_TOKEN must all be set in .env / App Settings.'
        )

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
    )
    # Exchange refresh token for a fresh access token
    credentials.refresh(Request())

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
