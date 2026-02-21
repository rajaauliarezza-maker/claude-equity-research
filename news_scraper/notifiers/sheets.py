"""
Google Sheets notifier — pushes flagged articles to a Google Spreadsheet.

Authentication (choose one):
  Option A — Service Account (recommended for automation):
    1. Create a service account in Google Cloud Console
    2. Enable Google Sheets API for your project
    3. Download the JSON key file
    4. Share your Google Sheet with the service account email
    5. Set env vars:
         GOOGLE_CREDENTIALS_FILE=/path/to/service_account.json
         GOOGLE_SHEET_ID=<your-spreadsheet-id>

  Option B — OAuth (for personal use / local machine):
    1. Create OAuth 2.0 credentials (Desktop app) in Google Cloud Console
    2. Download client_secrets.json
    3. Set env vars:
         GOOGLE_OAUTH_FILE=/path/to/client_secrets.json
         GOOGLE_SHEET_ID=<your-spreadsheet-id>
    First run will open a browser to authenticate; token cached locally.

Sheet structure (auto-created if sheet is empty):
  Tab "Flagged"  — only keyword-matched articles
  Tab "All"      — every scraped article

Columns (in order):
  Scraped At | Published At | Source | Sector | Ticker | Keywords |
  Title | URL | Summary
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Sheet column headers
HEADERS = [
    "Scraped At",
    "Published At",
    "Source",
    "Sector",
    "Ticker",
    "Keywords Matched",
    "Title",
    "URL",
    "Summary",
]

# Column index (0-based) of the URL — used for dedup checks
URL_COL_IDX = HEADERS.index("URL")


def _get_gspread_client(credentials_file: Optional[str], oauth_file: Optional[str]):
    """Return an authenticated gspread client."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials as SACredentials
        from google.oauth2.credentials import Credentials as OAuthCredentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import pickle
    except ImportError as e:
        raise ImportError(
            f"Missing dependency: {e}. "
            "Run: pip install gspread google-auth google-auth-oauthlib google-auth-httplib2"
        ) from e

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]

    # --- Service Account ---
    if credentials_file and os.path.exists(credentials_file):
        logger.info("Authenticating with service account: %s", credentials_file)
        creds = SACredentials.from_service_account_file(credentials_file, scopes=SCOPES)
        return gspread.authorize(creds)

    # --- OAuth ---
    if oauth_file and os.path.exists(oauth_file):
        token_path = os.path.join(os.path.dirname(oauth_file), "token.pickle")
        creds = None
        if os.path.exists(token_path):
            with open(token_path, "rb") as f:
                creds = pickle.load(f)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(oauth_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "wb") as f:
                pickle.dump(creds, f)
        logger.info("Authenticating with OAuth credentials")
        return gspread.authorize(creds)

    raise ValueError(
        "No valid credentials found.\n"
        "Set GOOGLE_CREDENTIALS_FILE (service account) or GOOGLE_OAUTH_FILE (OAuth)."
    )


def _ensure_tab(spreadsheet, tab_name: str):
    """Return worksheet, creating it with headers if it doesn't exist."""
    import gspread

    try:
        ws = spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=5000, cols=len(HEADERS))

    # Write headers if the sheet is empty
    if ws.row_count == 0 or not ws.row_values(1):
        ws.append_row(HEADERS, value_input_option="RAW")
        # Bold + freeze header row
        spreadsheet.batch_update({
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": ws.id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                                "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.8},
                                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor,foregroundColor)",
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": ws.id, "gridProperties": {"frozenRowCount": 1}},
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
            ]
        })
    return ws


def _get_existing_urls(ws) -> set[str]:
    """Fetch all URLs already in the sheet for dedup."""
    try:
        col = ws.col_values(URL_COL_IDX + 1)  # gspread is 1-indexed
        return set(col[1:])  # skip header
    except Exception:
        return set()


def _article_to_row(article: dict) -> list:
    """Convert an article dict to a sheet row."""
    kws = article.get("keywords_matched", "[]")
    if isinstance(kws, str):
        try:
            kws = ", ".join(json.loads(kws))
        except Exception:
            pass
    return [
        (article.get("scraped_at") or "")[:19],
        (article.get("published_at") or "")[:10],
        article.get("source", ""),
        article.get("sector", ""),
        article.get("ticker", ""),
        kws,
        article.get("title", ""),
        article.get("url", ""),
        article.get("summary", "") or "",
    ]


class SheetsNotifier:
    """
    Pushes articles from the local SQLite DB to Google Sheets.

    Parameters
    ----------
    sheet_id : str
        The Google Spreadsheet ID (from the URL).
    credentials_file : str, optional
        Path to service account JSON key. Defaults to GOOGLE_CREDENTIALS_FILE env var.
    oauth_file : str, optional
        Path to OAuth client_secrets.json. Defaults to GOOGLE_OAUTH_FILE env var.
    """

    def __init__(
        self,
        sheet_id: Optional[str] = None,
        credentials_file: Optional[str] = None,
        oauth_file: Optional[str] = None,
    ):
        self.sheet_id = sheet_id or os.environ.get("GOOGLE_SHEET_ID", "")
        self.credentials_file = credentials_file or os.environ.get("GOOGLE_CREDENTIALS_FILE", "")
        self.oauth_file = oauth_file or os.environ.get("GOOGLE_OAUTH_FILE", "")

        if not self.sheet_id:
            raise ValueError(
                "Sheet ID required. Set GOOGLE_SHEET_ID env var or pass sheet_id=."
            )

    def _connect(self):
        client = _get_gspread_client(self.credentials_file or None, self.oauth_file or None)
        return client.open_by_key(self.sheet_id)

    def push(
        self,
        articles: list[dict],
        tab_name: str = "Flagged",
        flagged_only: bool = True,
    ) -> tuple[int, int]:
        """
        Push articles to the specified tab.

        Returns (pushed_count, skipped_count).
        """
        if flagged_only:
            articles = [a for a in articles if a.get("is_flagged")]

        if not articles:
            logger.info("No articles to push.")
            return 0, 0

        spreadsheet = self._connect()
        ws = _ensure_tab(spreadsheet, tab_name)
        existing_urls = _get_existing_urls(ws)

        rows_to_add = []
        skipped = 0
        for art in articles:
            url = art.get("url", "")
            if url in existing_urls:
                skipped += 1
                continue
            rows_to_add.append(_article_to_row(art))
            existing_urls.add(url)

        if rows_to_add:
            ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")
            logger.info(
                "Pushed %d new rows to '%s' tab (skipped %d duplicates).",
                len(rows_to_add), tab_name, skipped,
            )
        else:
            logger.info("All %d articles already in sheet.", skipped)

        return len(rows_to_add), skipped

    def push_all(self, articles: list[dict]) -> dict:
        """
        Push flagged articles to 'Flagged' tab and all articles to 'All' tab.
        Returns counts dict.
        """
        flagged_pushed, flagged_skip = self.push(articles, tab_name="Flagged", flagged_only=True)
        all_pushed, all_skip = self.push(articles, tab_name="All", flagged_only=False)
        return {
            "flagged_pushed": flagged_pushed,
            "flagged_skipped": flagged_skip,
            "all_pushed": all_pushed,
            "all_skipped": all_skip,
        }
