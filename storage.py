"""
SQLite storage for caching Apollo results and managing approval queue.
"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

from config import config
from schema import ApprovalRequest, ApolloContact


def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_transaction():
    """Context manager for database transactions."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database tables."""
    with db_transaction() as conn:
        cursor = conn.cursor()

        # Company cache table - stores Apollo search results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_cache (
                domain TEXT PRIMARY KEY,
                contacts_json TEXT NOT NULL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Approval queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approval_queue (
                id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                domain TEXT NOT NULL,
                signal_summary TEXT NOT NULL,
                contact_id TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                contact_title TEXT,
                contact_email TEXT,
                personalized_subject TEXT NOT NULL,
                personalized_email TEXT NOT NULL,
                i18n_signals TEXT NOT NULL,
                slack_message_ts TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_approval_status
            ON approval_queue(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_domain_cache
            ON company_cache(domain, fetched_at)
        """)


def get_cached_contacts(domain: str) -> Optional[list[dict]]:
    """
    Get cached contacts for a domain if not expired.
    Returns None if cache miss or expired.
    """
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT contacts_json, fetched_at FROM company_cache WHERE domain = ?",
            (domain,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        # Check if cache is expired
        fetched_at = datetime.fromisoformat(row["fetched_at"])
        expiry = timedelta(days=config.CACHE_EXPIRY_DAYS)

        if datetime.now() - fetched_at > expiry:
            # Cache expired, delete it
            cursor.execute("DELETE FROM company_cache WHERE domain = ?", (domain,))
            return None

        return json.loads(row["contacts_json"])


def cache_contacts(domain: str, contacts: list[dict]):
    """Cache contacts for a domain."""
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO company_cache (domain, contacts_json, fetched_at)
            VALUES (?, ?, ?)
            """,
            (domain, json.dumps(contacts), datetime.now().isoformat())
        )


def save_approval_request(request: ApprovalRequest):
    """Save an approval request to the queue."""
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO approval_queue (
                id, company, domain, signal_summary, contact_id, contact_name,
                contact_title, contact_email, personalized_subject, personalized_email,
                i18n_signals, slack_message_ts, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.id, request.company, request.domain, request.signal_summary,
                request.contact_id, request.contact_name, request.contact_title,
                request.contact_email, request.personalized_subject, request.personalized_email,
                request.i18n_signals, request.slack_message_ts, request.status,
                datetime.now().isoformat()
            )
        )


def get_approval_request(request_id: str) -> Optional[ApprovalRequest]:
    """Get an approval request by ID."""
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM approval_queue WHERE id = ?",
            (request_id,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        return ApprovalRequest(**dict(row))


def update_approval_status(request_id: str, status: str, slack_ts: Optional[str] = None):
    """Update the status of an approval request."""
    with db_transaction() as conn:
        cursor = conn.cursor()
        if slack_ts:
            cursor.execute(
                """
                UPDATE approval_queue
                SET status = ?, slack_message_ts = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, slack_ts, datetime.now().isoformat(), request_id)
            )
        else:
            cursor.execute(
                """
                UPDATE approval_queue
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, datetime.now().isoformat(), request_id)
            )


def get_pending_requests() -> list[ApprovalRequest]:
    """Get all pending approval requests."""
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM approval_queue WHERE status = 'pending' ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        return [ApprovalRequest(**dict(row)) for row in rows]


def update_approval_email(request_id: str, subject: str, body: str):
    """Update the personalized email content for an approval request."""
    with db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE approval_queue
            SET personalized_subject = ?, personalized_email = ?, updated_at = ?
            WHERE id = ?
            """,
            (subject, body, datetime.now().isoformat(), request_id)
        )
