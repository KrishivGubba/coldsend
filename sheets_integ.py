"""
Google Sheets integration module for cold email automation.
Provides functions to read pending jobs, update status, etc.
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

# Configuration
SHEET_ID = "1qZaIABA_VQv1LWl9GBAoMDT0ii8FTB42b8ETl50DUKQ"
CREDENTIALS_FILE = "credentials.json"

# Column indices (0-based)
COL = {
    "company_name": 0,
    "company_linkedin_url": 1,
    "job_title": 2,
    "job_description": 3,
    "status": 4,
    "date_added": 5,
    "max_emails": 6,
    "profiles_found": 7,
    "emails_sent": 8,
    "notes": 9
}


@dataclass
class JobEntry:
    """Represents a row in the sheet."""
    row_number: int  # 1-indexed row in sheet
    company_name: str
    company_linkedin_url: str
    job_title: str
    job_description: str
    status: str
    date_added: str
    max_emails: int
    profiles_found: int
    emails_sent: int
    notes: str


_client = None
_worksheet = None


def _get_worksheet():
    """Get cached worksheet connection."""
    global _client, _worksheet
    if _worksheet is None:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        _client = gspread.authorize(creds)
        sheet = _client.open_by_key(SHEET_ID)
        _worksheet = sheet.sheet1
    return _worksheet


def _row_to_entry(row_number: int, row_data: list) -> JobEntry:
    """Convert a row of data to a JobEntry object."""
    # Pad row with empty strings if needed
    while len(row_data) < 10:
        row_data.append("")
    
    return JobEntry(
        row_number=row_number,
        company_name=row_data[COL["company_name"]] or "",
        company_linkedin_url=row_data[COL["company_linkedin_url"]] or "",
        job_title=row_data[COL["job_title"]] or "",
        job_description=row_data[COL["job_description"]] or "",
        status=row_data[COL["status"]] or "",
        date_added=row_data[COL["date_added"]] or "",
        max_emails=int(row_data[COL["max_emails"]] or 10),
        profiles_found=int(row_data[COL["profiles_found"]] or 0),
        emails_sent=int(row_data[COL["emails_sent"]] or 0),
        notes=row_data[COL["notes"]] or ""
    )


def get_pending_jobs() -> list[JobEntry]:
    """Get all jobs with status 'pending'."""
    ws = _get_worksheet()
    all_rows = ws.get_all_values()
    
    pending = []
    for i, row in enumerate(all_rows[1:], start=2):  # Skip header, 1-indexed
        if len(row) > COL["status"] and row[COL["status"]] == "pending":
            pending.append(_row_to_entry(i, row))
    
    return pending


def get_jobs_by_status(status: str) -> list[JobEntry]:
    """Get all jobs with a specific status."""
    ws = _get_worksheet()
    all_rows = ws.get_all_values()
    
    jobs = []
    for i, row in enumerate(all_rows[1:], start=2):
        if len(row) > COL["status"] and row[COL["status"]] == status:
            jobs.append(_row_to_entry(i, row))
    
    return jobs


def get_all_jobs() -> list[JobEntry]:
    """Get all jobs from the sheet."""
    ws = _get_worksheet()
    all_rows = ws.get_all_values()
    
    return [_row_to_entry(i, row) for i, row in enumerate(all_rows[1:], start=2) if any(row)]


def update_status(row_number: int, new_status: str):
    """Update the status of a job."""
    ws = _get_worksheet()
    col_letter = chr(ord('A') + COL["status"])
    ws.update(f"{col_letter}{row_number}", [[new_status]])


def update_profiles_found(row_number: int, count: int):
    """Update the profiles_found count for a job."""
    ws = _get_worksheet()
    col_letter = chr(ord('A') + COL["profiles_found"])
    ws.update(f"{col_letter}{row_number}", [[count]])


def update_emails_sent(row_number: int, count: int):
    """Update the emails_sent count for a job."""
    ws = _get_worksheet()
    col_letter = chr(ord('A') + COL["emails_sent"])
    ws.update(f"{col_letter}{row_number}", [[count]])


def increment_emails_sent(row_number: int):
    """Increment the emails_sent count by 1."""
    ws = _get_worksheet()
    col_letter = chr(ord('A') + COL["emails_sent"])
    cell = ws.acell(f"{col_letter}{row_number}")
    current = int(cell.value or 0)
    ws.update(f"{col_letter}{row_number}", [[current + 1]])


def add_job(
    company_name: str,
    company_linkedin_url: str,
    job_title: str,
    job_description: str,
    max_emails: int = 10,
    notes: str = ""
) -> int:
    """Add a new job to the sheet. Returns the row number."""
    ws = _get_worksheet()
    
    new_row = [
        company_name,
        company_linkedin_url,
        job_title,
        job_description,
        "pending",
        datetime.now().strftime("%Y-%m-%d"),
        max_emails,
        0,  # profiles_found
        0,  # emails_sent
        notes
    ]
    
    ws.append_row(new_row)
    return len(ws.get_all_values())


def add_note(row_number: int, note: str, append: bool = True):
    """Add or update notes for a job."""
    ws = _get_worksheet()
    col_letter = chr(ord('A') + COL["notes"])
    
    if append:
        current = ws.acell(f"{col_letter}{row_number}").value or ""
        if current:
            note = f"{current}; {note}"
    
    ws.update(f"{col_letter}{row_number}", [[note]])


# Convenience function for the polling service
def get_next_pending_job() -> Optional[JobEntry]:
    """Get the oldest pending job (first one in sheet order)."""
    pending = get_pending_jobs()
    return pending[0] if pending else None


# if __name__ == "__main__":
#     # Quick test
#     print("Testing sheets integration...")
    
#     jobs = get_all_jobs()
#     print(f"Total jobs in sheet: {len(jobs)}")
    
#     pending = get_pending_jobs()
#     print(f"Pending jobs: {len(pending)}")

#     add_job(
#         company_name="Test Company",
#         company_linkedin_url="https://www.linkedin.com/company/test-company",
#         job_title="Software Engineer",
#         job_description="Looking for a skilled software engineer.",
#         max_emails=5,
#         notes="Initial test entry."
#     )
    
#     for job in pending:
#         print(f"  - {job.company_name}: {job.job_title}")