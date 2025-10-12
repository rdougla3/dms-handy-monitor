import gspread
from datetime import datetime

CREDENTIALS_PATH = 'printer-monitoring-474822-bdfc6f0da109.json'
SPREADSHEET_NAME = "print-records"
WORKSHEET_NAME = "Sheet2"

import gspread
from datetime import datetime

class SheetClient:
    def __init__(self):
        self.credentials_path = CREDENTIALS_PATH
        self.spreadsheet_name = SPREADSHEET_NAME
        self.worksheet_name = WORKSHEET_NAME
        self._client = None
        self._spreadsheet = None
        self._sheet = None

    def _connect(self):
        """Lazy initialization of gspread client and worksheet."""
        if self._client is None:
            self._client = gspread.service_account(filename=self.credentials_path)
        if self._spreadsheet is None:
            self._spreadsheet = self._client.open(self.spreadsheet_name)
        if self._sheet is None:
            self._sheet = self._spreadsheet.worksheet(self.worksheet_name)
        return self._sheet

    def find_job_row(self, name: str, date: datetime):
        """
        Checks the sheet for a job with the given name and date.
        If found, returns the row number.
        If not found, returns the next available empty row number.
        """
        ws = self._connect()
        all_values = ws.get_all_values()

        for i, row in enumerate(all_values, start=1):
            if len(row) < 3:
                continue

            row_name = row[0].strip()
            row_date_str = row[2].strip()

            try:
                row_date = datetime.strptime(row_date_str, "%m/%d/%Y %H:%M")
            except Exception:
                continue

            if row_name == name and row_date == date:
                return i, row[7] if len(row) > 7 else ""

        return len(all_values) + 1, ""

    def update_job(self, job):
        """
        Finds the row for the given job by name and date.
        Overwrites that row’s data, or writes it to the next empty row if not found.
        """
        ws = self._connect()
        row, errors = self.find_job_row(job.name, job.date)
        values = [
            job.name,
            job.status,
            job.date.strftime("%m/%d/%Y %H:%M"),
            job.duration,
            job.machine,
            job.weight,
            ", ".join(job.materials),
            ", ".join(job.errors + [errors]) if errors not in job.errors else ", ".join(job.errors)
        ]
        ws.update(f"A{row}:H{row}", [values])