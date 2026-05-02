"""Google Sheets synchronization module."""
import logging
import os
import re
from datetime import date, datetime
from typing import Any, Callable, Iterable, Optional, Type

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from oauth2client.service_account import ServiceAccountCredentials
from sqlalchemy.orm import Session

import models
from config import config

logger = logging.getLogger(__name__)


RowMapper = Callable[[dict[str, Any]], dict[str, Any]]
GOOGLE_SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


class GoogleSheetsSync:
    """Handle full synchronization from Google Sheets to PostgreSQL."""

    def __init__(self):
        """Initialize Google Sheets client."""
        self.sheet = None
        self.credentials = None

    def authenticate(self):
        """Authenticate with Google Sheets."""
        try:
            if config.GOOGLE_AUTH_METHOD == "oauth":
                client = self._authenticate_with_oauth()
            elif config.GOOGLE_AUTH_METHOD == "service_account":
                client = self._authenticate_with_service_account()
            else:
                logger.error("Unsupported GOOGLE_AUTH_METHOD: %s", config.GOOGLE_AUTH_METHOD)
                return False

            if not client:
                return False

            if config.GOOGLE_SHEETS_URL:
                sheet_id = config.GOOGLE_SHEETS_URL.split("/d/")[1].split("/")[0]
                self.sheet = client.open_by_key(sheet_id)
                logger.info("Opened spreadsheet: %s", self.sheet.title)
                return True

            logger.error("Google Sheets URL not configured")
            return False
        except FileNotFoundError:
            logger.error(
                "Service account JSON not found at %s",
                config.GOOGLE_SHEETS_JSON_KEY_PATH,
            )
            return False
        except Exception as e:
            logger.error("Authentication failed: %s", e)
            return False

    def _authenticate_with_oauth(self):
        """Authenticate with a stored OAuth user token."""
        token_path = config.GOOGLE_OAUTH_TOKEN_PATH
        credentials = None

        if os.path.exists(token_path):
            credentials = Credentials.from_authorized_user_file(
                token_path,
                GOOGLE_SHEETS_SCOPES,
            )

        if not credentials:
            logger.error(
                "OAuth token not found at %s. Run `python auth_google.py` first.",
                token_path,
            )
            return None

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        if not credentials.valid:
            logger.error(
                "OAuth token is invalid or expired without a refresh token. "
                "Run `python auth_google.py` again."
            )
            return None

        self.credentials = credentials
        logger.info("Authenticated with Google Sheets using OAuth")
        return gspread.authorize(credentials)

    def _authenticate_with_service_account(self):
        """Authenticate with a service account key when available."""
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name(
            config.GOOGLE_SHEETS_JSON_KEY_PATH,
            scopes=scope,
        )
        logger.info("Authenticated with Google Sheets using service account")
        return gspread.authorize(self.credentials)

    def get_sheet_data(self, sheet_name: str):
        """Get all records from a specific sheet."""
        try:
            if not self.sheet:
                logger.error("Not authenticated with Google Sheets")
                return None

            worksheet = self.sheet.worksheet(sheet_name)
            data = worksheet.get_all_records()
            logger.info("Retrieved %s rows from sheet '%s'", len(data), sheet_name)
            return data
        except Exception as e:
            logger.error("Failed to get data from sheet '%s': %s", sheet_name, e)
            return None

    @staticmethod
    def _clean_str(value: Any, default: str = "") -> str:
        if value is None:
            return default
        return str(value).strip()

    @classmethod
    def _optional_str(cls, value: Any) -> Optional[str]:
        cleaned = cls._clean_str(value)
        return cleaned or None

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        text = str(value).strip()
        if not text:
            return None

        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                pass

        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()

    @staticmethod
    def _parse_float(value: Any, default: float = 0.0) -> float:
        if value in (None, ""):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        is_parenthesized_negative = text.startswith("(") and text.endswith(")")
        text = text.strip("()")
        text = re.sub(r"[^0-9.\-]", "", text)
        if text in ("", "-", "."):
            return default
        parsed = float(text)
        return -parsed if is_parenthesized_negative else parsed

    @staticmethod
    def _parse_bool(value: Any, default: bool = False) -> bool:
        if value in (None, ""):
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "yes", "y", "1"}

    @classmethod
    def _normalize_employment_type(cls, value: Any) -> str:
        text = cls._clean_str(value).lower().replace("_", " ").replace("-", " ")
        text = re.sub(r"\s+", " ", text)
        aliases = {
            "full time": "full-time",
            "fulltime": "full-time",
            "part time": "part-time",
            "parttime": "part-time",
            "contract": "contractor",
        }
        return aliases.get(text, text.replace(" ", "-"))

    @classmethod
    def _sheet_rows(cls, data: Iterable[dict[str, Any]], pk_field: str) -> list[dict[str, Any]]:
        """Drop empty rows and the workbook's human-readable description row."""
        rows = []
        for row in data:
            pk_value = cls._clean_str(row.get(pk_field))
            if not pk_value or pk_value.lower().startswith("pk"):
                continue
            rows.append(row)
        return rows

    def _write_sync_log(
        self,
        db: Session,
        table_name: str,
        rows_processed: int,
        inserted: int,
        updated: int,
        deleted: int,
        started_at: datetime,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        db.add(
            models.SyncLog(
                table_name=table_name,
                sync_type="full",
                rows_processed=rows_processed,
                rows_inserted=inserted,
                rows_updated=updated,
                rows_deleted=deleted,
                status=status,
                error_message=error_message,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )
        )

    def _sync_table(
        self,
        db: Session,
        sheet_name: str,
        model: Type[models.Base],
        pk_field: str,
        map_row: RowMapper,
    ) -> dict:
        """Full-sync one sheet into one table.

        Rows present in the sheet are inserted or updated. Rows missing from the
        sheet are soft-deleted in PostgreSQL so Google Sheet deletions are
        reflected locally without breaking foreign keys or audit history.
        """
        started_at = datetime.utcnow()
        data = self.get_sheet_data(sheet_name)
        if data is None:
            result = {"status": "failed", "rows": 0, "error": "sheet read failed"}
            self._write_sync_log(db, model.__tablename__, 0, 0, 0, 0, started_at, "failed", result["error"])
            db.commit()
            return result

        rows = self._sheet_rows(data, pk_field)
        sheet_ids = {self._clean_str(row.get(pk_field)) for row in rows}
        inserted, updated, deleted = 0, 0, 0

        try:
            for row in rows:
                row_id = self._clean_str(row.get(pk_field))
                existing = db.get(model, row_id)
                row_data = map_row(row)

                if existing:
                    for key, value in row_data.items():
                        setattr(existing, key, value)
                    if hasattr(existing, "is_deleted"):
                        existing.is_deleted = False
                        existing.deleted_at = None
                    existing.updated_at = datetime.utcnow()
                    updated += 1
                else:
                    db.add(model(**{pk_field: row_id}, **row_data))
                    inserted += 1

            existing_records = db.query(model).all()
            for record in existing_records:
                record_id = getattr(record, pk_field)
                if record_id in sheet_ids:
                    continue

                if hasattr(record, "is_deleted"):
                    if not record.is_deleted:
                        record.is_deleted = True
                        record.deleted_at = datetime.utcnow()
                        record.updated_at = datetime.utcnow()
                        deleted += 1
                else:
                    db.delete(record)
                    deleted += 1

            self._write_sync_log(
                db,
                model.__tablename__,
                len(rows),
                inserted,
                updated,
                deleted,
                started_at,
            )
            db.commit()
            logger.info(
                "%s: %s inserted, %s updated, %s deleted",
                model.__tablename__,
                inserted,
                updated,
                deleted,
            )
            return {
                "status": "success",
                "rows_processed": len(rows),
                "inserted": inserted,
                "updated": updated,
                "deleted": deleted,
            }
        except Exception as e:
            db.rollback()
            logger.error("Failed to sync %s: %s", model.__tablename__, e)
            try:
                self._write_sync_log(
                    db,
                    model.__tablename__,
                    len(rows),
                    inserted,
                    updated,
                    deleted,
                    started_at,
                    "failed",
                    str(e),
                )
                db.commit()
            except Exception:
                db.rollback()
            return {"status": "failed", "error": str(e), "rows_processed": len(rows)}

    def sync_revenue_streams(self, db: Session) -> dict:
        """Sync Revenue Streams."""
        return self._sync_table(
            db,
            "Revenue_Streams",
            models.RevenueStream,
            "revenue_stream_id",
            lambda row: {
                "stream_name": self._clean_str(row.get("stream_name")),
                "stream_type": self._clean_str(row.get("stream_type")),
                "pricing_model": self._clean_str(row.get("pricing_model")),
                "notes": self._optional_str(row.get("notes")),
            },
        )

    def sync_employees(self, db: Session) -> dict:
        """Sync Employees."""
        return self._sync_table(
            db,
            "Employees",
            models.Employee,
            "employee_id",
            lambda row: {
                "full_name": self._clean_str(row.get("full_name")),
                "role": self._clean_str(row.get("role")),
                "department": self._clean_str(row.get("department")),
                "employment_type": self._normalize_employment_type(row.get("employment_type")),
                "start_date": self._parse_date(row.get("start_date")),
                "end_date": self._parse_date(row.get("end_date")),
                "currency": self._clean_str(row.get("currency"), "EUR"),
                "is_active": self._parse_bool(row.get("is_active"), True),
                "notes": self._optional_str(row.get("notes")),
            },
        )

    def sync_projects(self, db: Session) -> dict:
        """Sync Projects."""
        return self._sync_table(
            db,
            "Projects",
            models.Project,
            "project_id",
            lambda row: {
                "project_name": self._clean_str(row.get("project_name")),
                "client_name": self._clean_str(row.get("client_name")),
                "project_type": self._clean_str(row.get("project_type")),
                "status": self._clean_str(row.get("status"), "active"),
                "start_date": self._parse_date(row.get("start_date")),
                "end_date": self._parse_date(row.get("end_date")),
                "contracted_budget": self._parse_float(row.get("contracted_budget")),
                "revenue_stream_id": self._clean_str(row.get("revenue_stream_id")),
                "currency": self._clean_str(row.get("currency"), "EUR"),
                "responsible_employee_id": self._optional_str(row.get("responsible_employee_id")),
                "notes": self._optional_str(row.get("notes")),
            },
        )

    def sync_revenue_transactions(self, db: Session) -> dict:
        """Sync Revenue Transactions."""
        return self._sync_table(
            db,
            "Revenue_Transactions",
            models.RevenueTransaction,
            "transaction_id",
            lambda row: {
                "invoice_number": self._clean_str(row.get("invoice_number")),
                "date": self._parse_date(row.get("date")),
                "project_id": self._clean_str(row.get("project_id")),
                "amount": self._parse_float(row.get("amount")),
                "payment_status": self._clean_str(row.get("payment_status"), "invoiced"),
                "payment_date": self._parse_date(row.get("payment_date")),
                "notes": self._optional_str(row.get("notes")),
            },
        )

    def sync_cogs_transactions(self, db: Session) -> dict:
        """Sync COGS Transactions."""
        return self._sync_table(
            db,
            "COGS_Transactions",
            models.CogsTransaction,
            "transaction_id",
            lambda row: {
                "invoice_number": self._clean_str(row.get("invoice_number")),
                "date": self._parse_date(row.get("date")),
                "vendor_name": self._clean_str(row.get("vendor_name")),
                "amount": self._parse_float(row.get("amount")),
                "cost_category": self._clean_str(row.get("cost_category")),
                "payment_status": self._clean_str(row.get("payment_status"), "pending"),
                "payment_date": self._parse_date(row.get("payment_date")),
                "project_id": self._clean_str(row.get("project_id")),
                "notes": self._optional_str(row.get("notes")),
            },
        )

    def sync_overhead_transactions(self, db: Session) -> dict:
        """Sync Overhead Transactions."""
        return self._sync_table(
            db,
            "Overhead_Transactions",
            models.OverheadTransaction,
            "transaction_id",
            lambda row: {
                "date": self._parse_date(row.get("date")),
                "overhead_category": self._clean_str(row.get("overhead_category")),
                "sub_category": self._optional_str(row.get("sub_category")),
                "vendor_name": self._clean_str(row.get("vendor_name")),
                "invoice_number": self._optional_str(row.get("invoice_number")),
                "amount": self._parse_float(row.get("amount")),
                "payment_status": self._clean_str(row.get("payment_status"), "pending"),
                "payment_date": self._parse_date(row.get("payment_date")),
                "employee_id": self._optional_str(row.get("employee_id")),
                "notes": self._optional_str(row.get("notes")),
            },
        )

    def sync_bank_movements(self, db: Session) -> dict:
        """Sync Bank Cash Movements."""
        return self._sync_table(
            db,
            "Bank_Cash_Movements",
            models.BankCashMovement,
            "movement_id",
            lambda row: {
                "date": self._parse_date(row.get("date")),
                "bank_account": self._clean_str(row.get("bank_account")),
                "movement_type": self._clean_str(row.get("movement_type")),
                "amount": self._parse_float(row.get("amount")),
                "counterparty": self._optional_str(row.get("counterparty")),
                "description": self._optional_str(row.get("description")),
                "reference_transaction_id": self._optional_str(row.get("reference_transaction_id")),
                "is_frozen": self._parse_bool(row.get("is_frozen")),
                "frozen_reason": self._optional_str(row.get("frozen_reason")),
                "balance_after": self._parse_float(row.get("balance_after")) if row.get("balance_after") not in (None, "") else None,
                "notes": self._optional_str(row.get("notes")),
            },
        )

    def sync_salaries(self, db: Session) -> dict:
        """Sync Salaries."""
        return self._sync_table(
            db,
            "Salaries",
            models.Salary,
            "salary_id",
            lambda row: {
                "date": self._parse_date(row.get("date")),
                "gross_salary": self._parse_float(row.get("gross_salary")),
                "currency": self._clean_str(row.get("currency"), "EUR"),
                "cadence": self._clean_str(row.get("cadence"), "monthly"),
                "employee_id": self._clean_str(row.get("employee_id")),
                "notes": self._optional_str(row.get("notes")),
            },
        )

    def sync_all(self, db: Session) -> dict:
        """Sync all tables from Google Sheets."""
        logger.info("Starting full synchronization from Google Sheets")

        results = {
            "revenue_streams": self.sync_revenue_streams(db),
            "employees": self.sync_employees(db),
            "projects": self.sync_projects(db),
            "revenue_transactions": self.sync_revenue_transactions(db),
            "cogs_transactions": self.sync_cogs_transactions(db),
            "overhead_transactions": self.sync_overhead_transactions(db),
            "bank_movements": self.sync_bank_movements(db),
            "salaries": self.sync_salaries(db),
        }

        logger.info("Synchronization complete")
        return results
