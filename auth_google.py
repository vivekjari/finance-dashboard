"""Run the one-time Google OAuth flow for Sheets sync."""
import os

from google_auth_oauthlib.flow import InstalledAppFlow

from config import config
from sync_sheets import GOOGLE_SHEETS_SCOPES


def main() -> int:
    """Create or replace the local OAuth token used by the sync job."""
    client_secret_path = config.GOOGLE_OAUTH_CLIENT_SECRET_PATH
    token_path = config.GOOGLE_OAUTH_TOKEN_PATH

    if not os.path.exists(client_secret_path):
        print(f"OAuth client secret not found: {client_secret_path}")
        print("Download it from Google Cloud Console and place it at that path.")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(
        client_secret_path,
        GOOGLE_SHEETS_SCOPES,
    )
    credentials = flow.run_local_server(port=0, prompt="consent")

    os.makedirs(os.path.dirname(token_path), exist_ok=True)
    with open(token_path, "w", encoding="utf-8") as token_file:
        token_file.write(credentials.to_json())

    print(f"OAuth token saved: {token_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
