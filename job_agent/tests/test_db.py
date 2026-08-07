from job_agent import db


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


async def test_get_application_returns_none_when_never_recorded():
	assert await db.get_application('https://boards.greenhouse.io/co/jobs/does-not-exist') is None


async def test_get_application_returns_most_recently_recorded_row():
	dedup_key = 'https://boards.greenhouse.io/co/jobs/4'
	await db.record_application(
		dedup_key=dedup_key,
		company='Co',
		title='Engineer',
		url=dedup_key,
		ats_platform='greenhouse',
		status='screened_pass',
		match_score=85,
		match_reasoning='Good fit.',
	)

	application = await db.get_application(dedup_key)

	assert application is not None
	assert application['status'] == 'screened_pass'
	assert application['match_score'] == 85
