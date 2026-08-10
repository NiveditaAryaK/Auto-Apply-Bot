import asyncio

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


async def test_concurrent_first_uploads_still_leave_exactly_one_primary():
	"""Regression test for the check-then-act race in _insert_resume_sync: firing many concurrent
	insert_resume() calls against an empty table must still leave exactly one row marked
	primary, never zero (nobody claims it) and never more than one (multiple see count == 0)."""
	await asyncio.gather(*(db.insert_resume(f'resume{i}.pdf', f'/data/resume{i}.pdf') for i in range(20)))

	resumes = await db.list_resumes()
	assert len(resumes) == 20
	assert sum(1 for r in resumes if r['is_primary']) == 1


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


async def test_create_run_if_none_active_succeeds_when_none_running():
	run_id = await db.create_run_if_none_active()

	assert run_id is not None
	active = await db.get_active_run()
	assert active is not None and active['id'] == run_id


async def test_create_run_if_none_active_returns_none_when_one_is_running():
	first_id = await db.create_run_if_none_active()

	second_id = await db.create_run_if_none_active()

	assert first_id is not None
	assert second_id is None


async def test_create_run_if_none_active_is_atomic_under_concurrency():
	"""Regression test for the check-then-act race: firing many concurrent calls must only ever
	let exactly one of them win, never zero and never more than one."""
	results = await asyncio.gather(*(db.create_run_if_none_active() for _ in range(20)))

	winners = [r for r in results if r is not None]
	assert len(winners) == 1

	runs = await db.list_runs()
	assert sum(1 for r in runs if r['status'] == 'running') == 1


async def test_update_run_sets_current_step():
	run_id = await db.create_run()

	await db.update_run(run_id, current_step='Screening 2/5: Backend Engineer at Acme')

	run = await db.get_run(run_id)
	assert run is not None
	assert run['current_step'] == 'Screening 2/5: Backend Engineer at Acme'
	assert run['status'] == 'running'  # unaffected by an update that only sets current_step


async def test_fail_stale_running_runs_sweeps_running_rows_to_failed():
	"""Regression test for a run whose background task died with a previous process (a crash,
	--reload restart, or deploy) -- the row is left stuck at status='running' forever with no
	live task to ever finish it, which would otherwise block every future run via
	create_run_if_none_active. This is meant to run once at API startup."""
	stale_id = await db.create_run()
	await db.update_run(stale_id, current_step='Screening 2/5: Backend Engineer at Acme')

	await db.fail_stale_running_runs()

	run = await db.get_run(stale_id)
	assert run is not None
	assert run['status'] == 'failed'
	assert run['finished_at'] is not None
	assert run['error']
	assert await db.get_active_run() is None


async def test_fail_stale_running_runs_leaves_completed_runs_alone():
	run_id = await db.create_run()
	await db.update_run(run_id, status='completed', finished_at='2026-01-01T00:00:00+00:00', postings_found=1)

	await db.fail_stale_running_runs()

	run = await db.get_run(run_id)
	assert run is not None
	assert run['status'] == 'completed'


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
