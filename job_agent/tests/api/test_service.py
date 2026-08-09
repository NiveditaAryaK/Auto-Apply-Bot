from httpx import ASGITransport, AsyncClient

from job_agent import db
from job_agent.api.service import app


def _client() -> AsyncClient:
	return AsyncClient(transport=ASGITransport(app=app), base_url='http://test')


async def test_upload_resume_returns_it_as_primary_when_first():
	async with _client() as client:
		response = await client.post(
			'/api/resumes', files={'file': ('resume.pdf', b'%PDF-1.4 fake', 'application/pdf')}
		)

	assert response.status_code == 201
	body = response.json()
	assert body['filename'] == 'resume.pdf'
	assert body['is_primary'] is True


async def test_upload_second_resume_defaults_to_non_primary():
	async with _client() as client:
		await client.post('/api/resumes', files={'file': ('r1.pdf', b'one', 'application/pdf')})
		response = await client.post('/api/resumes', files={'file': ('r2.pdf', b'two', 'application/pdf')})

	assert response.json()['is_primary'] is False


async def test_upload_rejects_unsupported_file_type():
	async with _client() as client:
		response = await client.post('/api/resumes', files={'file': ('resume.txt', b'text', 'text/plain')})

	assert response.status_code == 400


async def test_list_resumes_returns_uploaded_resumes():
	async with _client() as client:
		await client.post('/api/resumes', files={'file': ('r1.pdf', b'one', 'application/pdf')})
		response = await client.get('/api/resumes')

	assert response.status_code == 200
	assert [r['filename'] for r in response.json()] == ['r1.pdf']


async def test_set_primary_resume_swaps_the_flag():
	async with _client() as client:
		first = (await client.post('/api/resumes', files={'file': ('r1.pdf', b'one', 'application/pdf')})).json()
		second = (await client.post('/api/resumes', files={'file': ('r2.pdf', b'two', 'application/pdf')})).json()

		response = await client.patch(f'/api/resumes/{second["id"]}/primary')

	assert response.status_code == 200
	assert response.json()['is_primary'] is True
	assert (await db.get_resume(first['id']))['is_primary'] == 0


async def test_set_primary_resume_404s_for_missing_id():
	async with _client() as client:
		response = await client.patch('/api/resumes/999/primary')

	assert response.status_code == 404


async def test_delete_non_primary_resume_removes_it():
	async with _client() as client:
		await client.post('/api/resumes', files={'file': ('r1.pdf', b'one', 'application/pdf')})
		second = (await client.post('/api/resumes', files={'file': ('r2.pdf', b'two', 'application/pdf')})).json()

		response = await client.delete(f'/api/resumes/{second["id"]}')

	assert response.status_code == 204
	assert await db.get_resume(second['id']) is None


async def test_delete_primary_resume_is_rejected():
	async with _client() as client:
		first = (await client.post('/api/resumes', files={'file': ('r1.pdf', b'one', 'application/pdf')})).json()

		response = await client.delete(f'/api/resumes/{first["id"]}')

	assert response.status_code == 400
	assert await db.get_resume(first['id']) is not None


async def test_list_applications_returns_recorded_rows():
	await db.record_application(
		dedup_key='https://boards.greenhouse.io/co/jobs/1',
		company='Co',
		title='Engineer',
		url='https://boards.greenhouse.io/co/jobs/1',
		ats_platform='greenhouse',
		status='applied',
	)

	async with _client() as client:
		response = await client.get('/api/applications')

	assert response.status_code == 200
	assert [a['title'] for a in response.json()] == ['Engineer']


async def test_get_latest_run_404s_when_no_runs_exist():
	async with _client() as client:
		response = await client.get('/api/runs/latest')

	assert response.status_code == 404


async def test_get_run_404s_for_missing_id():
	async with _client() as client:
		response = await client.get('/api/runs/999')

	assert response.status_code == 404


async def test_trigger_run_409s_when_a_run_is_already_active():
	await db.create_run()

	async with _client() as client:
		response = await client.post('/api/runs')

	assert response.status_code == 409
