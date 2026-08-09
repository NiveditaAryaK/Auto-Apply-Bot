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


async def test_list_applications_returns_newest_first():
	await db.record_application(
		dedup_key='https://boards.greenhouse.io/co/jobs/5', company='Co', title='A', url='u1', ats_platform='greenhouse', status='applied'
	)
	await db.record_application(
		dedup_key='https://boards.greenhouse.io/co/jobs/6', company='Co', title='B', url='u2', ats_platform='greenhouse', status='applied'
	)

	applications = await db.list_applications()

	assert len(applications) >= 2
	assert applications[0]['title'] == 'B'
	assert applications[1]['title'] == 'A'


async def test_first_uploaded_resume_is_always_primary():
	resume_id = await db.insert_resume('resume.pdf', '/data/resume.pdf', is_primary=False)

	resume = await db.get_resume(resume_id)

	assert resume is not None
	assert resume['is_primary'] == 1


async def test_second_resume_defaults_to_non_primary():
	await db.insert_resume('resume1.pdf', '/data/resume1.pdf')
	second_id = await db.insert_resume('resume2.pdf', '/data/resume2.pdf')

	resume = await db.get_resume(second_id)

	assert resume is not None
	assert resume['is_primary'] == 0


async def test_inserting_a_second_resume_as_primary_unmarks_the_first():
	first_id = await db.insert_resume('resume1.pdf', '/data/resume1.pdf')
	second_id = await db.insert_resume('resume2.pdf', '/data/resume2.pdf', is_primary=True)

	first = await db.get_resume(first_id)
	second = await db.get_resume(second_id)

	assert first is not None and first['is_primary'] == 0
	assert second is not None and second['is_primary'] == 1


async def test_set_primary_resume_swaps_the_flag():
	first_id = await db.insert_resume('resume1.pdf', '/data/resume1.pdf')
	second_id = await db.insert_resume('resume2.pdf', '/data/resume2.pdf')

	await db.set_primary_resume(second_id)

	first = await db.get_resume(first_id)
	second = await db.get_resume(second_id)
	assert first is not None and first['is_primary'] == 0
	assert second is not None and second['is_primary'] == 1


async def test_list_resumes_returns_all_in_upload_order():
	await db.insert_resume('resume1.pdf', '/data/resume1.pdf')
	await db.insert_resume('resume2.pdf', '/data/resume2.pdf')

	resumes = await db.list_resumes()

	assert [r['filename'] for r in resumes] == ['resume1.pdf', 'resume2.pdf']


async def test_delete_resume_removes_it():
	resume_id = await db.insert_resume('resume.pdf', '/data/resume.pdf')

	await db.delete_resume(resume_id)

	assert await db.get_resume(resume_id) is None


async def test_get_active_run_is_none_until_a_run_starts():
	assert await db.get_active_run() is None


async def test_create_run_marks_it_active_until_updated():
	run_id = await db.create_run()

	active = await db.get_active_run()

	assert active is not None
	assert active['id'] == run_id
	assert active['status'] == 'running'


async def test_update_run_completes_it_and_clears_active_run():
	run_id = await db.create_run()

	await db.update_run(run_id, status='completed', finished_at='2026-01-01T00:00:00+00:00', postings_found=3, applied_count=1)

	run = await db.get_run(run_id)
	assert run is not None
	assert run['status'] == 'completed'
	assert run['postings_found'] == 3
	assert run['applied_count'] == 1
	assert await db.get_active_run() is None


async def test_list_runs_returns_newest_first():
	first_id = await db.create_run()
	second_id = await db.create_run()

	runs = await db.list_runs()

	assert runs[0]['id'] == second_id
	assert runs[1]['id'] == first_id
