import pytest

from job_agent import config, db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
	monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
	monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'job_agent.sqlite3')


async def test_mark_seen_and_is_seen_roundtrip():
	assert await db.is_seen('https://boards.greenhouse.io/co/jobs/1') is False
	await db.mark_seen('https://boards.greenhouse.io/co/jobs/1', 'Co', 'Engineer', 'https://boards.greenhouse.io/co/jobs/1', 'greenhouse')
	assert await db.is_seen('https://boards.greenhouse.io/co/jobs/1') is True


async def test_mark_seen_is_idempotent():
	dedup_key = 'https://boards.greenhouse.io/co/jobs/2'
	await db.mark_seen(dedup_key, 'Co', 'Engineer', dedup_key, 'greenhouse')
	await db.mark_seen(dedup_key, 'Co', 'Engineer', dedup_key, 'greenhouse')
	assert await db.is_seen(dedup_key) is True


async def test_record_application_does_not_raise():
	await db.record_application(
		dedup_key='https://boards.greenhouse.io/co/jobs/3',
		company='Co',
		title='Engineer',
		url='https://boards.greenhouse.io/co/jobs/3',
		ats_platform='greenhouse',
		status='applied',
		match_score=90,
		match_reasoning='strong match',
	)


async def test_question_cache_miss_then_hit():
	assert await db.get_cached_answer('greenhouse', 'expected salary') is None
	await db.cache_answer('greenhouse', 'expected salary', 'expected_salary', '150000')
	assert await db.get_cached_answer('greenhouse', 'expected salary') == ('expected_salary', '150000')


async def test_question_cache_upsert_overwrites_previous_answer():
	await db.cache_answer('lever', 'notice period', 'notice_period_days', '30')
	await db.cache_answer('lever', 'notice period', 'notice_period_days', '60')
	assert await db.get_cached_answer('lever', 'notice period') == ('notice_period_days', '60')
