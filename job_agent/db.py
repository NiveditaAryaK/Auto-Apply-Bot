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
	cover_letter_path TEXT,
	status TEXT NOT NULL,
	notes TEXT,
	applied_at TEXT
);

CREATE TABLE IF NOT EXISTS question_cache (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	ats_platform TEXT NOT NULL,
	normalized_label TEXT NOT NULL,
	canonical_field TEXT NOT NULL,
	answer_text TEXT NOT NULL,
	updated_at TEXT NOT NULL,
	UNIQUE(ats_platform, normalized_label)
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
	cover_letter_path: str | None = None,
	notes: str | None = None,
) -> None:
	conn = _connect()
	try:
		conn.execute(
			'INSERT INTO applications '
			'(dedup_key, company, title, url, ats_platform, match_score, match_reasoning, '
			' resume_path, cover_letter_path, status, notes, applied_at) '
			'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
			(
				dedup_key,
				company,
				title,
				url,
				ats_platform,
				match_score,
				match_reasoning,
				resume_path,
				cover_letter_path,
				status,
				notes,
				_now(),
			),
		)
		conn.commit()
	finally:
		conn.close()


def _get_cached_answer_sync(ats_platform: str, normalized_label: str) -> tuple[str, str] | None:
	conn = _connect()
	try:
		row = conn.execute(
			'SELECT canonical_field, answer_text FROM question_cache WHERE ats_platform = ? AND normalized_label = ?',
			(ats_platform, normalized_label),
		).fetchone()
		return (row[0], row[1]) if row is not None else None
	finally:
		conn.close()


def _cache_answer_sync(ats_platform: str, normalized_label: str, canonical_field: str, answer_text: str) -> None:
	conn = _connect()
	try:
		conn.execute(
			'INSERT INTO question_cache (ats_platform, normalized_label, canonical_field, answer_text, updated_at) '
			'VALUES (?, ?, ?, ?, ?) '
			'ON CONFLICT(ats_platform, normalized_label) DO UPDATE SET '
			'canonical_field = excluded.canonical_field, answer_text = excluded.answer_text, updated_at = excluded.updated_at',
			(ats_platform, normalized_label, canonical_field, answer_text, _now()),
		)
		conn.commit()
	finally:
		conn.close()


async def is_seen(dedup_key: str) -> bool:
	return await asyncio.to_thread(_is_seen_sync, dedup_key)


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
	cover_letter_path: str | None = None,
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
		cover_letter_path,
		notes,
	)


async def get_cached_answer(ats_platform: str, normalized_label: str) -> tuple[str, str] | None:
	return await asyncio.to_thread(_get_cached_answer_sync, ats_platform, normalized_label)


async def cache_answer(ats_platform: str, normalized_label: str, canonical_field: str, answer_text: str) -> None:
	await asyncio.to_thread(_cache_answer_sync, ats_platform, normalized_label, canonical_field, answer_text)
