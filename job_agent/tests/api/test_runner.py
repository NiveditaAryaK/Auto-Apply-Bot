import asyncio
from pathlib import Path

from job_agent import db
from job_agent.api import runner
from job_agent.apply_agent import ApplicationOutcome


async def _wait_until_finished(run_id: int, timeout: float = 2.0) -> dict:
	loop = asyncio.get_event_loop()
	deadline = loop.time() + timeout
	while loop.time() < deadline:
		run = await db.get_run(run_id)
		assert run is not None
		if run['status'] != 'running':
			return run
		await asyncio.sleep(0.01)
	raise AssertionError(f'run {run_id} never left running status')


async def test_start_run_raises_when_a_run_is_already_active():
	await db.create_run()

	try:
		await runner.start_run()
		raise AssertionError('expected RuntimeError')
	except RuntimeError as e:
		assert 'already in progress' in str(e)


async def test_start_run_records_applied_count_from_pipeline_outcomes(monkeypatch):
	async def fake_pipeline_run(llm=None, role_resumes=None, on_progress=None):
		return [
			ApplicationOutcome(submitted=True, questions_encountered=[]),
			ApplicationOutcome(submitted=False, questions_encountered=['salary?']),
		]

	monkeypatch.setattr(runner.pipeline, 'run', fake_pipeline_run)

	run_id = await runner.start_run()
	run = await _wait_until_finished(run_id)

	assert run['status'] == 'completed'
	assert run['applied_count'] == 1


async def test_start_run_records_screening_counts_from_applications_written_this_run(monkeypatch):
	async def fake_pipeline_run(llm=None, role_resumes=None, on_progress=None):
		await db.record_application(
			dedup_key='https://boards.greenhouse.io/co/jobs/pass',
			company='Co',
			title='Pass',
			url='https://boards.greenhouse.io/co/jobs/pass',
			ats_platform='greenhouse',
			status='screened_pass',
			match_score=90,
		)
		await db.record_application(
			dedup_key='https://boards.greenhouse.io/co/jobs/reject',
			company='Co',
			title='Reject',
			url='https://boards.greenhouse.io/co/jobs/reject',
			ats_platform='greenhouse',
			status='screened_reject',
			match_score=40,
		)
		return []

	monkeypatch.setattr(runner.pipeline, 'run', fake_pipeline_run)

	run_id = await runner.start_run()
	run = await _wait_until_finished(run_id)

	assert run['status'] == 'completed'
	assert run['postings_found'] == 2
	assert run['screened_pass'] == 1
	assert run['screened_reject'] == 1
	assert run['applied_count'] == 0


async def test_start_run_records_error_on_failure(monkeypatch):
	async def fake_pipeline_run(llm=None, role_resumes=None, on_progress=None):
		raise ValueError('exactly one primary resume required')

	monkeypatch.setattr(runner.pipeline, 'run', fake_pipeline_run)

	run_id = await runner.start_run()
	run = await _wait_until_finished(run_id)

	assert run['status'] == 'failed'
	assert 'exactly one primary' in run['error']


async def test_concurrent_start_run_calls_only_let_one_through(monkeypatch):
	"""Regression test for the check-then-act race between db.get_active_run() and
	db.create_run(): firing many concurrent start_run() calls must only ever let exactly one
	succeed, with the rest raising RuntimeError, never two runs launched at once. The fake
	pipeline blocks on an Event so the winning run can't finish (and free up the active-run slot)
	before all 20 concurrent calls have been attempted."""
	release = asyncio.Event()

	async def fake_pipeline_run(llm=None, role_resumes=None, on_progress=None):
		await release.wait()
		return []

	monkeypatch.setattr(runner.pipeline, 'run', fake_pipeline_run)

	results = await asyncio.gather(*(runner.start_run() for _ in range(20)), return_exceptions=True)

	succeeded = [r for r in results if isinstance(r, int)]
	failed = [r for r in results if isinstance(r, RuntimeError)]
	assert len(succeeded) == 1
	assert len(failed) == 19

	release.set()
	await _wait_until_finished(succeeded[0])


async def test_start_run_publishes_pipeline_progress_onto_the_run_row(monkeypatch):
	seen_current_step_while_running = None

	async def fake_pipeline_run(llm=None, role_resumes=None, on_progress=None):
		nonlocal seen_current_step_while_running
		await on_progress('Searching job boards for new postings...')
		seen_current_step_while_running = (await db.get_run(run_id))['current_step']
		return []

	monkeypatch.setattr(runner.pipeline, 'run', fake_pipeline_run)

	run_id = await runner.start_run()
	await _wait_until_finished(run_id)

	assert seen_current_step_while_running == 'Searching job boards for new postings...'


async def test_start_run_builds_role_resumes_from_uploaded_resumes(monkeypatch):
	await db.insert_resume('resume.pdf', '/data/resume.pdf', is_primary=True)

	seen_role_resumes = []

	async def fake_pipeline_run(llm=None, role_resumes=None, on_progress=None):
		seen_role_resumes.append(role_resumes)
		return []

	monkeypatch.setattr(runner.pipeline, 'run', fake_pipeline_run)

	run_id = await runner.start_run()
	await _wait_until_finished(run_id)

	assert len(seen_role_resumes) == 1
	[role_resumes] = seen_role_resumes
	assert len(role_resumes) == 1
	assert role_resumes[0].resume_path == Path('/data/resume.pdf')
	assert role_resumes[0].is_primary is True
