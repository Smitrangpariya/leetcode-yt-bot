"""Run ONCE on your own computer. Creates token.json (keep it secret; paste it into the YOUTUBE_TOKEN_JSON secret)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow
import config
from pipeline.youtube import SCOPES

flow = InstalledAppFlow.from_client_secrets_file(str(config.CLIENT_SECRET_FILE), SCOPES)
creds = flow.run_local_server(port=0)
config.TOKEN_FILE.write_text(creds.to_json())
print("Saved", config.TOKEN_FILE)
