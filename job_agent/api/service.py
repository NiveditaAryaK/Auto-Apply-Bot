from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from uuid_extensions import uuid7str

from job_agent import config, db
from job_agent.api import runner
from job_agent.api.views import ApplicationOut, ResumeOut, RunOut


@asynccontextmanager
async def _lifespan(app: FastAPI):
	# A process only just starting up can't have any run's background task actually in flight, so
	# a 'running' row found here is necessarily stale (left behind by a crash, --reload restart,
	# or deploy) -- see db.fail_stale_running_runs.
	await db.fail_stale_running_runs()
	yield


app = FastAPI(title='job_agent', lifespan=_lifespan)

# Vite dev server default ports -- this is a single-user local tool, not a public deployment.
app.add_middleware(
	CORSMiddleware,
	allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
	allow_methods=['*'],
	allow_headers=['*'],
)

_ALLOWED_RESUME_SUFFIXES = ('.pdf', '.docx')


def _resume_out(row: dict) -> ResumeOut:
	"""Builds the response DTO from explicit fields rather than ResumeOut.model_validate(row) --
	the resumes table also carries stored_path (the server's absolute filesystem path), which
	shouldn't be exposed to the client."""
	return ResumeOut(id=row['id'], filename=row['filename'], is_primary=bool(row['is_primary']), uploaded_at=row['uploaded_at'])


@app.post('/api/resumes', response_model=ResumeOut, status_code=201)
async def upload_resume(file: UploadFile = File(...), is_primary: bool = Form(False)) -> ResumeOut:
	original_name = file.filename or ''
	suffix = Path(original_name).suffix.lower()
	if suffix not in _ALLOWED_RESUME_SUFFIXES:
		raise HTTPException(400, f'Resume must be one of {_ALLOWED_RESUME_SUFFIXES}, got {suffix!r}')

	config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
	stored_path = config.UPLOAD_DIR / f'{uuid7str()}{suffix}'
	stored_path.write_bytes(await file.read())

	resume_id = await db.insert_resume(filename=original_name, stored_path=str(stored_path), is_primary=is_primary)
	return _resume_out(await db.get_resume(resume_id))


@app.get('/api/resumes', response_model=list[ResumeOut])
async def list_resumes() -> list[ResumeOut]:
	return [_resume_out(row) for row in await db.list_resumes()]


@app.patch('/api/resumes/{resume_id}/primary', response_model=ResumeOut)
async def set_primary_resume(resume_id: int) -> ResumeOut:
	if await db.get_resume(resume_id) is None:
		raise HTTPException(404, 'Resume not found')
	await db.set_primary_resume(resume_id)
	return _resume_out(await db.get_resume(resume_id))


@app.delete('/api/resumes/{resume_id}', status_code=204)
async def delete_resume(resume_id: int) -> None:
	resume = await db.get_resume(resume_id)
	if resume is None:
		raise HTTPException(404, 'Resume not found')
	if resume['is_primary']:
		raise HTTPException(400, 'Cannot delete the primary resume -- set a different resume as primary first')
	await db.delete_resume(resume_id)
	Path(resume['stored_path']).unlink(missing_ok=True)


@app.get('/api/applications', response_model=list[ApplicationOut])
async def list_applications() -> list[ApplicationOut]:
	return [ApplicationOut.model_validate(row) for row in await db.list_applications()]


@app.post('/api/runs', response_model=RunOut, status_code=201)
async def trigger_run() -> RunOut:
	try:
		run_id = await runner.start_run()
	except RuntimeError as e:
		raise HTTPException(409, str(e))
	return RunOut.model_validate(await db.get_run(run_id))


@app.get('/api/runs/latest', response_model=RunOut)
async def get_latest_run() -> RunOut:
	runs = await db.list_runs()
	if not runs:
		raise HTTPException(404, 'No runs yet')
	return RunOut.model_validate(runs[0])


@app.get('/api/runs/{run_id}', response_model=RunOut)
async def get_run(run_id: int) -> RunOut:
	run = await db.get_run(run_id)
	if run is None:
		raise HTTPException(404, 'Run not found')
	return RunOut.model_validate(run)
