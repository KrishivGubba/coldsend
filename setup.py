"""
Setup script to initialize the Google Sheet with proper columns and formatting.
Run this once to set up your sheet.
"""

import gspread
from google.oauth2.service_account import Credentials

# Configuration
SHEET_ID = "1qZaIABA_VQv1LWl9GBAoMDT0ii8FTB42b8ETl50DUKQ"
CREDENTIALS_FILE = "credentials.json"  # Path to your service account JSON


raise Exception("This is a setup script. Please run it directly to set up your Google Sheet.") #remove line to run

# Column definitions
COLUMNS = [
    "company_name",
    "company_linkedin_url",
    "job_title", 
    "job_description",
    "status",
    "date_added",
    "max_emails",
    "profiles_found",
    "emails_sent",
    "notes"
]

# Valid status values (for reference)
VALID_STATUSES = ["pending", "scraping", "emailing", "done", "paused"]


def get_client():
    """Authenticate and return gspread client."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)


def setup_sheet():
    """Set up the sheet with columns and formatting."""
    client = get_client()
    sheet = client.open_by_key(SHEET_ID)
    worksheet = sheet.sheet1
    
    # Clear existing content
    worksheet.clear()
    
    # Set header row
    worksheet.update("A1", [COLUMNS])
    
    # Format header row (bold)
    worksheet.format("A1:J1", {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
    })
    
    # Set column widths for readability
    column_widths = {
        "A": 150,  # company_name
        "B": 300,  # company_linkedin_url
        "C": 200,  # job_title
        "D": 400,  # job_description
        "E": 100,  # status
        "F": 120,  # date_added
        "G": 100,  # max_emails
        "H": 120,  # profiles_found
        "I": 100,  # emails_sent
        "J": 200,  # notes
    }
    
    requests = []
    for i, (col, width) in enumerate(column_widths.items()):
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": worksheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": i,
                    "endIndex": i + 1
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize"
            }
        })
    
    # Add data validation for status column
    requests.append({
        "setDataValidation": {
            "range": {
                "sheetId": worksheet.id,
                "startRowIndex": 1,
                "endRowIndex": 1000,
                "startColumnIndex": 4,  # status column (E)
                "endColumnIndex": 5
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": s} for s in VALID_STATUSES]
                },
                "showCustomUi": True,
                "strict": True
            }
        }
    })
    
    # Execute batch update
    sheet.batch_update({"requests": requests})
    
    # Freeze header row
    worksheet.freeze(rows=1)
    
    print("✓ Sheet setup complete!")
    print(f"  Columns: {', '.join(COLUMNS)}")
    print(f"  Status dropdown values: {', '.join(VALID_STATUSES)}")
    print(f"\n  Sheet URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == "__main__":
    setup_sheet()