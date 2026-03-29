"""
PDF upload helper for dry-marking snapshots — uses Telegram Bot API.

No OAuth, no user login, no shared drives — just two string tokens.

Required settings / .env variables:
  TELEGRAM_BOT_TOKEN  – token from @BotFather (e.g. 123456:ABC-xyz...)
  TELEGRAM_CHAT_ID    – numeric ID of the private channel/group the bot is in

One-time setup (takes ~3 minutes):
  1. Open Telegram, search for @BotFather, send /newbot, follow the prompts.
     Copy the token you receive.  Set TELEGRAM_BOT_TOKEN in .env.
  2. Create a private Telegram channel (or group) called e.g. "OSCE Dry Marking".
  3. Add your bot to the channel as an Administrator.
  4. Get the channel's chat ID:
       a. Forward any message from the channel to @userinfobot, or
       b. Temporarily add @RawDataBot to the channel, send a message, it shows the chat ID.
     Channel chat IDs are negative, e.g. -1001234567890.
     Set TELEGRAM_CHAT_ID in .env.
  5. Deploy / restart the server.  That's it.

Each submitted PDF will be sent to that channel as a document named
"{student} - {exam} - {session}.pdf", accessible to anyone in the channel.
Telegram stores it permanently and you can search/download it any time.
"""
import logging

logger = logging.getLogger(__name__)


def upload_pdf(pdf_bytes: bytes, filename: str) -> str:
    """
    Send *pdf_bytes* as a Telegram document to the configured chat.

    Returns the Telegram file_id of the uploaded document.
    Raises on any error so the caller can handle gracefully.
    """
    import requests
    from django.conf import settings

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', '')

    if not token or not chat_id:
        raise ValueError(
            'TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env / App Settings. '
            'See examiner/google_drive.py for setup instructions.'
        )

    url = f'https://api.telegram.org/bot{token}/sendDocument'

    response = requests.post(
        url,
        data={'chat_id': chat_id, 'caption': filename},
        files={'document': (filename, pdf_bytes, 'application/pdf')},
        timeout=60,
    )

    if not response.ok:
        raise RuntimeError(
            f'Telegram upload failed ({response.status_code}): {response.text}'
        )

    result = response.json()
    file_id = result['result']['document']['file_id']
    logger.info('Dry-marking PDF sent to Telegram: %s (file_id=%s)', filename, file_id)
    return file_id
