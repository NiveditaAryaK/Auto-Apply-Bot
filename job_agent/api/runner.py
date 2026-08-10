import asyncio
from datetime import datetime, timezone
from pathlib import Path

from job_agent import config, db, pipeline


def _role_resumes_from_rows(rows: list[dict]) -> list[config.RoleResume]:
	return [config.RoleResume(resume_path=Path(row['stored_path']), is_primary=bool(row['is_primary'])) for row in rows]


async def start_run() -> int:
	"""Kick off a full pipeline run (discovery -> screening -> apply) as a background task and
	return the new runs.id immediately, so the caller (the API layer) can return without waiting
	for a potentially long-running browser-use apply step. Raises RuntimeError if a run is
	already in flight -- the API layer translates that into a 409.

	Uses db.create_run_if_none_active() rather than a get_active_run() check followed by a
	separate create_run() insert: two concurrent calls (e.g. a double-clicked Run button) could
	otherwise both observe "no active run" before either insert commits and both launch a
	pipeline run."""
	run_id = await db.create_run_if_none_active()
	if run_id is None:
		raise RuntimeError('A run is already in progress')

	role_resumes = _role_resumes_from_rows(await db.list_resumes())
	asyncio.create_task(_execute_run(run_id, role_resumes))
	return run_id


async def _execute_run(run_id: int, role_resumes: list[config.RoleResume]) -> None:
	"""Runs pipeline.run() and records counters/errors onto the runs row. Postings-found/
	screened-pass/screened-reject counts come from the applications rows this run itself wrote
	(applied_at >= this run's local start time) rather than a richer pipeline.run() return value,
	since only one run executes at a time (guarded by db.get_active_run() in start_run) so every
	row written after that timestamp unambiguously belongs to this run."""
	started_at = datetime.now(timezone.utc).isoformat()
	try:
		outcomes = await pipeline.run(role_resumes=role_resumes)

		this_run_rows = [a for a in await db.list_applications() if a['applied_at'] >= started_at]
		screening_rows = [a for a in this_run_rows if a['status'] in ('screened_pass', 'screened_reject')]

		await db.update_run(
			run_id,
			status='completed',
			finished_at=datetime.now(timezone.utc).isoformat(),
			postings_found=len(screening_rows),
			screened_pass=sum(1 for a in screening_rows if a['status'] == 'screened_pass'),
			screened_reject=sum(1 for a in screening_rows if a['status'] == 'screened_reject'),
			applied_count=sum(1 for o in outcomes if o.submitted),
		)
	except Exception as e:
		await db.update_run(
			run_id,
			status='failed',
			finished_at=datetime.now(timezone.utc).isoformat(),
			error=str(e),
		)
