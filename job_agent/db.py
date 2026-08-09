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

CREATE TABLE IF NOT EXISTS resumes (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	filename TEXT NOT NULL,
	stored_path TEXT NOT NULL,
	is_primary INTEGER NOT NULL DEFAULT 0,
	uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	started_at TEXT NOT NULL,
	finished_at TEXT,
	status TEXT NOT NULL,
	postings_found INTEGER,
	screened_pass INTEGER,
	screened_reject INTEGER,
	applied_count INTEGER,
	error TEXT
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


def _list_applications_sync() -> list[dict]:
	conn = _connect()
	try:
		conn.row_factory = sqlite3.Row
		rows = conn.execute('SELECT * FROM applications ORDER BY id DESC').fetchall()
		return [dict(row) for row in rows]
	finally:
		conn.close()


def _insert_resume_sync(filename: str, stored_path: str, is_primary: bool = False) -> int:
	conn = _connect()
	try:
		count = conn.execute('SELECT COUNT(*) FROM resumes').fetchone()[0]
		is_primary = is_primary or count == 0  # first resume uploaded is always primary
		if is_primary:
			conn.execute('UPDATE resumes SET is_primary = 0')
		cursor = conn.execute(
			'INSERT INTO resumes (filename, stored_path, is_primary, uploaded_at) VALUES (?, ?, ?, ?)',
			(filename, stored_path, int(is_primary), _now()),
		)
		conn.commit()
		return cursor.lastrowid
	finally:
		conn.close()


def _list_resumes_sync() -> list[dict]:
	conn = _connect()
	try:
		conn.row_factory = sqlite3.Row
		rows = conn.execute('SELECT * FROM resumes ORDER BY id').fetchall()
		return [dict(row) for row in rows]
	finally:
		conn.close()


def _get_resume_sync(resume_id: int) -> dict | None:
	conn = _connect()
	try:
		conn.row_factory = sqlite3.Row
		row = conn.execute('SELECT * FROM resumes WHERE id = ?', (resume_id,)).fetchone()
		return dict(row) if row is not None else None
	finally:
		conn.close()


def _set_primary_resume_sync(resume_id: int) -> None:
	conn = _connect()
	try:
		conn.execute('UPDATE resumes SET is_primary = 0')
		conn.execute('UPDATE resumes SET is_primary = 1 WHERE id = ?', (resume_id,))
		conn.commit()
	finally:
		conn.close()


def _delete_resume_sync(resume_id: int) -> None:
	conn = _connect()
	try:
		conn.execute('DELETE FROM resumes WHERE id = ?', (resume_id,))
		conn.commit()
	finally:
		conn.close()


def _create_run_sync() -> int:
	conn = _connect()
	try:
		cursor = conn.execute(
			"INSERT INTO runs (started_at, status) VALUES (?, 'running')",
			(_now(),),
		)
		conn.commit()
		return cursor.lastrowid
	finally:
		conn.close()


def _update_run_sync(
	run_id: int,
	status: str | None = None,
	finished_at: str | None = None,
	postings_found: int | None = None,
	screened_pass: int | None = None,
	screened_reject: int | None = None,
	applied_count: int | None = None,
	error: str | None = None,
) -> None:
	fields = {
		'status': status,
		'finished_at': finished_at,
		'postings_found': postings_found,
		'screened_pass': screened_pass,
		'screened_reject': screened_reject,
		'applied_count': applied_count,
		'error': error,
	}
	fields = {k: v for k, v in fields.items() if v is not None}
	if not fields:
		return
	conn = _connect()
	try:
		set_clause = ', '.join(f'{k} = ?' for k in fields)
		conn.execute(f'UPDATE runs SET {set_clause} WHERE id = ?', (*fields.values(), run_id))
		conn.commit()
	finally:
		conn.close()


def _list_runs_sync() -> list[dict]:
	conn = _connect()
	try:
		conn.row_factory = sqlite3.Row
		rows = conn.execute('SELECT * FROM runs ORDER BY id DESC').fetchall()
		return [dict(row) for row in rows]
	finally:
		conn.close()


def _get_run_sync(run_id: int) -> dict | None:
	conn = _connect()
	try:
		conn.row_factory = sqlite3.Row
		row = conn.execute('SELECT * FROM runs WHERE id = ?', (run_id,)).fetchone()
		return dict(row) if row is not None else None
	finally:
		conn.close()


def _get_active_run_sync() -> dict | None:
	conn = _connect()
	try:
		conn.row_factory = sqlite3.Row
		row = conn.execute("SELECT * FROM runs WHERE status = 'running' ORDER BY id DESC LIMIT 1").fetchone()
		return dict(row) if row is not None else None
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


async def list_applications() -> list[dict]:
	"""Every applications row, newest first -- backs the dashboard table."""
	return await asyncio.to_thread(_list_applications_sync)


async def insert_resume(filename: str, stored_path: str, is_primary: bool = False) -> int:
	"""Record an uploaded resume. The first resume ever uploaded is always made primary
	regardless of is_primary, so the "exactly one primary" invariant never has a gap. Marking a
	resume primary here unmarks any previous primary in the same transaction."""
	return await asyncio.to_thread(_insert_resume_sync, filename, stored_path, is_primary)


async def list_resumes() -> list[dict]:
	return await asyncio.to_thread(_list_resumes_sync)


async def get_resume(resume_id: int) -> dict | None:
	return await asyncio.to_thread(_get_resume_sync, resume_id)


async def set_primary_resume(resume_id: int) -> None:
	await asyncio.to_thread(_set_primary_resume_sync, resume_id)


async def delete_resume(resume_id: int) -> None:
	await asyncio.to_thread(_delete_resume_sync, resume_id)


async def create_run() -> int:
	"""Insert a new runs row with status='running' and return its id."""
	return await asyncio.to_thread(_create_run_sync)


async def update_run(
	run_id: int,
	status: str | None = None,
	finished_at: str | None = None,
	postings_found: int | None = None,
	screened_pass: int | None = None,
	screened_reject: int | None = None,
	applied_count: int | None = None,
	error: str | None = None,
) -> None:
	await asyncio.to_thread(
		_update_run_sync,
		run_id,
		status,
		finished_at,
		postings_found,
		screened_pass,
		screened_reject,
		applied_count,
		error,
	)


async def list_runs() -> list[dict]:
	return await asyncio.to_thread(_list_runs_sync)


async def get_run(run_id: int) -> dict | None:
	return await asyncio.to_thread(_get_run_sync, run_id)


async def get_active_run() -> dict | None:
	"""The current in-flight run (status='running'), or None -- used to reject overlapping
	POST /api/runs triggers rather than letting two browser-use Agent sessions race."""
	return await asyncio.to_thread(_get_active_run_sync)
