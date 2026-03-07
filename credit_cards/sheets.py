"""
Google Sheets adapter using gspread.

Cell mapping mirrors Financial.xlsx exactly:
  - Row 1:  card names (cols F,H,J,...) and flags (cols G,I,K,...); C1 = years_counted
  - Row 2:  Annual EV (output, per card col)
  - Row 3:  Points Earned (output, per card col)
  - Row 4:  Annual Point Earn (output, per card col)
  - Row 5:  2nd Year+ Annual EV (output, per card col)
  - Col E, rows 2-5: wallet totals (Annual EV, Points Earned, Annual Pts, 2nd Year EV)
  - Rows 19-35, col E: annual spend per category (input)

Authentication
--------------
Two modes are supported, controlled by GOOGLE_AUTH_METHOD in .env:

  oauth (default)
    Browser-based OAuth 2.0. On first run, opens a browser to authorize access.
    Credentials are cached in the file set by GOOGLE_TOKEN_PATH (default: .oauth_token.json).
    Requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env (from an OAuth 2.0 Desktop
    app credential — no service account key needed).

  service_account
    Traditional service account JSON key file.
    Requires GOOGLE_CREDENTIALS_PATH pointing to the downloaded JSON key.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import gspread
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# 26 cards × 2 cols each, starting at col F (index 5, gspread col 6)
# Card data cols: F=6, H=8, J=10, ... (every 2nd col, 1-indexed)
# Card flag cols: G=7, I=9, K=11, ...
CARD_DATA_COLS = list(range(6, 58, 2))   # [6, 8, 10, ..., 56] — 26 cols (gspread 1-indexed)
CARD_FLAG_COLS = list(range(7, 59, 2))   # [7, 9, 11, ..., 57]

# Row numbers (gspread 1-indexed, matching xlsx row numbers)
ROW_CARD_NAMES   = 1
ROW_ANNUAL_EV    = 2
ROW_PTS_EARNED   = 3
ROW_ANNUAL_PTS   = 4
ROW_2ND_YEAR_EV  = 5
ROW_CREDIT_VAL   = 6
ROW_ANNUAL_FEE   = 7
ROW_SUB_POINTS   = 8
ROW_ANNUAL_BONUS = 9
ROW_SUB_MIN_SPEND = 10
ROW_SUB_MONTHS   = 11
ROW_SUB_ROS      = 12   # return on spend (computed)
ROW_SUB_EXTRA    = 13
ROW_SUB_SPEND_PTS = 14
ROW_SUB_OPP_COST = 15
ROW_OPP_COST_ABS = 16
ROW_AVG_MULT     = 17
ROW_CPP          = 18

# Category spend: rows 19-35, col E (gspread col 5)
CATEGORY_SPEND_ROW_START = 19
CATEGORY_SPEND_ROW_END   = 35
COL_SPEND = 5   # col E

# Wallet summary totals go in col E rows 2-5
COL_TOTALS = 5   # col E

# years_counted: row 1, col C (gspread col 3)
CELL_YEARS_COUNTED = (1, 3)


def _get_client() -> gspread.Client:
    """
    Build a gspread client using OAuth (default) or a service account key,
    controlled by GOOGLE_AUTH_METHOD in .env.
    """
    method = os.environ.get("GOOGLE_AUTH_METHOD", "oauth").lower()

    if method == "service_account":
        creds_path = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES
        )
        return gspread.authorize(creds)

    # --- OAuth 2.0 (default) ---
    token_path = os.environ.get("GOOGLE_TOKEN_PATH", ".oauth_token.json")
    creds: Optional[Credentials] = None

    # Load cached token if it exists
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh or run the browser auth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_id = os.environ.get("GOOGLE_CLIENT_ID")
            client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
            if not client_id or not client_secret:
                raise RuntimeError(
                    "OAuth credentials missing. Set GOOGLE_CLIENT_ID and "
                    "GOOGLE_CLIENT_SECRET in credit_cards/.env, or set "
                    "GOOGLE_AUTH_METHOD=service_account and provide a key file."
                )
            # Support both "web" and "installed" (Desktop) OAuth client types.
            # Web clients must use a localhost redirect; installed clients can
            # also use run_local_server, so we treat them the same way here.
            client_config = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": ["http://localhost"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)

        # Cache the token for future runs
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return gspread.authorize(creds)


def _open_worksheet(spreadsheet_id: str, sheet_name: str) -> gspread.Worksheet:
    client = _get_client()
    sh = client.open_by_key(spreadsheet_id)
    return sh.worksheet(sheet_name)


# ---------------------------------------------------------------------------
# Input reading
# ---------------------------------------------------------------------------


class SheetInputs:
    years_counted: int
    selected_cards: dict[str, bool]   # card_name -> True/False
    spend: dict[str, float]           # category -> annual_spend
    card_col_map: dict[str, int]      # card_name -> gspread data col (1-indexed)


def read_inputs(spreadsheet_id: str, sheet_name: str = "Credit Card Tool") -> SheetInputs:
    """
    Read years_counted, card selection flags, and category spend from the sheet.
    Returns a SheetInputs object.
    """
    ws = _open_worksheet(spreadsheet_id, sheet_name)

    # Fetch the entire sheet in one API call for efficiency
    all_values = ws.get_all_values()  # list of lists, 0-indexed

    def cell(row: int, col: int):
        """1-indexed row/col -> all_values value (empty string if missing)."""
        r, c = row - 1, col - 1
        try:
            return all_values[r][c]
        except IndexError:
            return ""

    inputs = SheetInputs()

    # years_counted (C1)
    raw_years = cell(*CELL_YEARS_COUNTED)
    try:
        inputs.years_counted = int(float(raw_years))
    except (ValueError, TypeError):
        inputs.years_counted = 2

    # Card names and flags (row 1)
    inputs.selected_cards = {}
    inputs.card_col_map = {}
    for data_col, flag_col in zip(CARD_DATA_COLS, CARD_FLAG_COLS):
        name = cell(ROW_CARD_NAMES, data_col)
        flag = cell(ROW_CARD_NAMES, flag_col)
        if name:
            inputs.selected_cards[name] = _parse_bool(flag)
            inputs.card_col_map[name] = data_col

    # Category spend (col E, rows 19-35)
    inputs.spend = {}
    for row in range(CATEGORY_SPEND_ROW_START, CATEGORY_SPEND_ROW_END + 1):
        # Category label is in col D (col 4)
        category = cell(row, 4)
        spend_val = cell(row, COL_SPEND)
        if category:
            try:
                inputs.spend[category] = float(spend_val) if spend_val else 0.0
            except (ValueError, TypeError):
                inputs.spend[category] = 0.0

    return inputs


def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().upper() in ("TRUE", "1", "YES")
    return bool(val)


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------


def write_outputs(
    spreadsheet_id: str,
    wallet_result,  # WalletResult from calculator
    card_col_map: dict[str, int],   # card_name -> gspread col (1-indexed)
    sheet_name: str = "Credit Card Tool",
) -> int:
    """
    Write computed results back to the sheet.
    Returns the number of cells updated.
    """
    ws = _open_worksheet(spreadsheet_id, sheet_name)

    updates: list[dict] = []

    def queue(row: int, col: int, value) -> None:
        cell_addr = gspread.utils.rowcol_to_a1(row, col)
        updates.append({"range": cell_addr, "values": [[value]]})

    # --- Wallet totals in col E ---
    queue(ROW_ANNUAL_EV,   COL_TOTALS, wallet_result.total_annual_ev)
    queue(ROW_PTS_EARNED,  COL_TOTALS, wallet_result.total_points_earned)
    queue(ROW_ANNUAL_PTS,  COL_TOTALS, wallet_result.total_annual_pts)
    queue(ROW_2ND_YEAR_EV, COL_TOTALS, 0)  # no wallet-level 2nd-year aggregate in sheet

    # --- Per-card results ---
    for cr in wallet_result.card_results:
        col = card_col_map.get(cr.card_name)
        if col is None:
            continue

        if cr.selected:
            queue(ROW_ANNUAL_EV,    col, cr.annual_ev)
            queue(ROW_PTS_EARNED,   col, cr.total_points)
            queue(ROW_ANNUAL_PTS,   col, cr.annual_point_earn)
            queue(ROW_2ND_YEAR_EV,  col, cr.second_year_ev)
            queue(ROW_CREDIT_VAL,   col, cr.credit_valuation)
            queue(ROW_AVG_MULT,     col, cr.avg_spend_multiplier)
            queue(ROW_SUB_EXTRA,    col, cr.sub_extra_spend)
            queue(ROW_SUB_OPP_COST, col, cr.sub_opportunity_cost)
            queue(ROW_OPP_COST_ABS, col, cr.opp_cost_abs)
        else:
            # Zero out computed cells for deselected cards
            for row in (ROW_ANNUAL_EV, ROW_PTS_EARNED, ROW_ANNUAL_PTS,
                        ROW_2ND_YEAR_EV, ROW_CREDIT_VAL, ROW_AVG_MULT,
                        ROW_SUB_EXTRA, ROW_SUB_OPP_COST, ROW_OPP_COST_ABS):
                queue(row, col, 0)

    if not updates:
        return 0

    ws.batch_update(updates, value_input_option="USER_ENTERED")
    return len(updates)


# ---------------------------------------------------------------------------
# Convenience: push a card selection update to the sheet
# ---------------------------------------------------------------------------


def write_card_flags(
    spreadsheet_id: str,
    selected_card_names: list[str],
    card_col_map: dict[str, int],
    sheet_name: str = "Credit Card Tool",
) -> None:
    """
    Set the flag (TRUE/FALSE) in row 1 for each card.
    selected_card_names: list of card names that should be TRUE.
    """
    ws = _open_worksheet(spreadsheet_id, sheet_name)
    updates: list[dict] = []
    selected_set = set(selected_card_names)

    for name, data_col in card_col_map.items():
        flag_col = data_col + 1
        cell_addr = gspread.utils.rowcol_to_a1(ROW_CARD_NAMES, flag_col)
        updates.append({
            "range": cell_addr,
            "values": [[name in selected_set]],
        })

    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")
