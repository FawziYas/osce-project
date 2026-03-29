"""
One-time helper to obtain an OAuth 2.0 refresh token for Google Drive uploads.

Run this ONCE from your local machine:
    python get_drive_token.py

It will open a browser window asking you to sign into the Google account that
owns the Drive folder where PDFs should be saved.  After you approve, it
prints the refresh token — copy it into your .env file.

Prerequisites
-------------
1.  Go to https://console.cloud.google.com/
2.  Select the project (cryptic-lattice-491710-c4 or create a new one).
3.  APIs & Services → Enable APIs → enable "Google Drive API".
4.  APIs & Services → Credentials → "+ Create Credentials" → OAuth client ID
        Application type: Desktop app
        Name: OSCE Drive Uploader (or anything)
        Click Create → copy "Client ID" and "Client secret".
5.  In .env set (temporarily, before running this script):
        GOOGLE_OAUTH_CLIENT_ID=<paste client id>
        GOOGLE_OAUTH_CLIENT_SECRET=<paste client secret>
6.  Run this script.  Approve in the browser.
7.  Copy the GOOGLE_OAUTH_REFRESH_TOKEN value printed below into .env.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Read client credentials from .env or environment
# ---------------------------------------------------------------------------
try:
    from dotenv import dotenv_values
    env = dotenv_values('.env')
except ImportError:
    env = {}

CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID') or env.get('GOOGLE_OAUTH_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET') or env.get('GOOGLE_OAUTH_CLIENT_SECRET', '')

if not CLIENT_ID or not CLIENT_SECRET:
    print(
        '\nERROR: GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set '
        'in .env before running this script.\n'
        'See the instructions at the top of this file.\n'
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Run the OAuth flow
# ---------------------------------------------------------------------------
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print(
        '\nERROR: google-auth-oauthlib is not installed.\n'
        'Run:  pip install google-auth-oauthlib\n'
    )
    sys.exit(1)

SCOPES = ['https://www.googleapis.com/auth/drive.file']

client_config = {
    'installed': {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'redirect_uris': ['urn:ietf:wg:oauth:2.0:oob', 'http://localhost'],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)

print('\nOpening browser for Google authorisation...')
print('Sign in with the Google account that OWNS the Drive folder.\n')

# run_local_server opens http://localhost for the redirect
credentials = flow.run_local_server(port=0, prompt='consent', access_type='offline')

print('\n' + '=' * 60)
print('SUCCESS!  Add these lines to your .env file:')
print('=' * 60)
print(f'GOOGLE_OAUTH_CLIENT_ID={CLIENT_ID}')
print(f'GOOGLE_OAUTH_CLIENT_SECRET={CLIENT_SECRET}')
print(f'GOOGLE_OAUTH_REFRESH_TOKEN={credentials.refresh_token}')
print('=' * 60)
print('\nAlso add to Azure App Service → Configuration → Application Settings.')
