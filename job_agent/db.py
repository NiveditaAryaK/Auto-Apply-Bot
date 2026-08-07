import asyncio
import sqlite3
from datetime import datetime, timezone

from job_agent import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	dedup_key TEXT UNIQUE NOT NULL,
	company TEXT NOT NULL,
	title TEXT NOT NULL,
	url TEXT NOT NULL,
	ats_platform TEXT NOT NULL,
	first_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	dedup_key TEXT NOT NULL,
	company TEXT NOT NULL,
	title TEXT NOT NULL,
	url TEXT NOT NULL,
	ats_platform TEXT NOT NULL,
	match_score INTEGER,
	match_reasoning TEXT,
	resume_path TEXT,
	status TEXT NOT NULL,
	notes TEXT,
	applied_at TEXT
);
"""


def _now() -> str:
	return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
	config.DATA_DIR.mkdir(parents=True, exist_ok=True)
	conn = sqlite3.connect(config.DB_PATH)
	conn.execute('PRAGMA journal_mode=WAL')
	conn.executescript(_SCHEMA)
	return conn


def _is_seen_sync(dedup_key: str) -> bool:
	conn = _connect()
	try:
		row = conn.execute('SELECT 1 FROM seen_jobs WHERE dedup_key = ?', (dedup_key,)).fetchone()
		return row is not None
	finally:
		conn.close()


def _mark_seen_sync(dedup_key: str, company: str, title: str, url: str, ats_platform: str) -> None:
	conn = _connect()
	try:
		conn.execute(
			'INSERT OR IGNORE INTO seen_jobs (dedup_key, company, title, url, ats_platform, first_seen_at) '
			'VALUES (?, ?, ?, ?, ?, ?)',
			(dedup_key, company, title, url, ats_platform, _now()),
		)
		conn.commit()
	finally:
		conn.close()


def _record_application_sync(
	dedup_key: str,
	company: str,
	title: str,
	url: str,
	ats_platform: str,
	status: str,
	match_score: int | None = None,
	match_reasoning: str | None = None,
	resume_path: str | None = None,
	notes: str | None = None,
) -> None:
	conn = _connect()
	try:
		conn.execute(
			'INSERT INTO applications '
			'(dedup_key, company, title, url, ats_platform, match_score, match_reasoning, '
			' resume_path, status, notes, applied_at) '
			'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
			(
				dedup_key,
				company,
				title,
				url,
				ats_platform,
				match_score,
				match_reasoning,
				resume_path,
				status,
				notes,
				_now(),
			),
		)
		conn.commit()
	finally:
		conn.close()


def _get_application_sync(dedup_key: str) -> dict | None:
	conn = _connect()
	try:
		conn.row_factory = sqlite3.Row
		row = conn.execute(
			'SELECT * FROM applications WHERE dedup_key = ? ORDER BY id DESC LIMIT 1', (dedup_key,)
		).fetchone()
		return dict(row) if row is not None else None
	finally:
		conn.close()


def _get_recent_applied_urls_sync(since_iso: str) -> list[str]:
	conn = _connect()
	try:
		rows = conn.execute(
			"SELECT url FROM applications WHERE status = 'applied' AND applied_at >= ?", (since_iso,)
		).fetchall()
		return [row[0] for row in rows]
	finally:
		conn.close()


async def is_seen(dedup_key: str) -> bool:
	return await asyncio.to_thread(_is_seen_sync, dedup_key)


async def get_application(dedup_key: str) -> dict | None:
	"""Most recent applications row for this posting, or None if it's never been recorded."""
	return await asyncio.to_thread(_get_application_sync, dedup_key)


async def get_recent_applied_urls(since_iso: str) -> list[str]:
	"""URLs of every application successfully submitted (status='applied') at or after
	since_iso -- used to enforce config.RATE_LIMITS per domain."""
	return await asyncio.to_thread(_get_recent_applied_urls_sync, since_iso)


async def mark_seen(dedup_key: str, company: str, title: str, url: str, ats_platform: str) -> None:
	await asyncio.to_thread(_mark_seen_sync, dedup_key, company, title, url, ats_platform)


async def record_application(
	dedup_key: str,
	company: str,
	title: str,
	url: str,
	ats_platform: str,
	status: str,
	match_score: int | None = None,
	match_reasoning: str | None = None,
	resume_path: str | None = None,
	notes: str | None = None,
) -> None:
	await asyncio.to_thread(
		_record_application_sync,
		dedup_key,
		company,
		title,
		url,
		ats_platform,
		status,
		match_score,
		match_reasoning,
		resume_path,
		notes,
	)
