"""
store.py — In-memory job store with progress tracking.

Production migration path:
  user_credits → Postgres `users` table  (add credits column)
  jobs         → Postgres `jobs` table + Redis pub/sub for real-time status

To migrate, replace every read/write in this file with async DB calls.
The rest of the codebase imports only from this module, so the interface
is stable and won't need changes elsewhere.
"""

from typing import Optional, Dict


# ─── In-memory stores ─────────────────────────────────────────────────────────
user_credits: Dict[str, int] = {}
jobs: Dict[str, dict] = {}


# ─── Credit operations ────────────────────────────────────────────────────────

def get_credits(email: str) -> int:
    return user_credits.get(email, 0)


def set_credits(email: str, amount: int) -> None:
    user_credits[email] = amount


def add_credits(email: str, amount: int) -> int:
    user_credits[email] = user_credits.get(email, 0) + amount
    return user_credits[email]


def deduct_credit(email: str) -> None:
    user_credits[email] = max(0, user_credits.get(email, 0) - 1)


def refund_credit(email: str) -> None:
    user_credits[email] = user_credits.get(email, 0) + 1


# ─── Job operations ───────────────────────────────────────────────────────────

def create_job(job_id: str) -> None:
    jobs[job_id] = {
        "status":        "queued",
        "video_type":    None,
        "video_url":     None,
        "caption":       None,
        "cta":           None,
        "error":         None,
        "progress":      0,         # 0–100
        "status_detail": None,      # human-readable step description
    }


def update_job(job_id: str, **kwargs) -> None:
    if job_id in jobs:
        jobs[job_id].update(kwargs)


def get_job(job_id: str) -> Optional[dict]:
    return jobs.get(job_id)


def list_jobs_for_user(email: str) -> list:
    """Returns all jobs that belong to a user (by prefix convention)."""
    # NOTE: In production, query DB with WHERE user_email = email
    return [
        {"job_id": jid, **jdata}
        for jid, jdata in jobs.items()
        if email in jid  # naive match — replace with proper user ID
    ]