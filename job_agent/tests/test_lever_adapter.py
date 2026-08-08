from pytest_httpserver import HTTPServer

from job_agent.discovery.lever import LeverAdapter


async def test_fetch_all_parses_postings():
	with HTTPServer() as server:
		server.expect_request('/v0/postings/examplecoinc', query_string='mode=json').respond_with_json(
			[
				{
					'text': 'Senior Backend Engineer',
					'categories': {'location': 'Remote'},
					'hostedUrl': 'https://jobs.lever.co/examplecoinc/abc-123',
					'descriptionPlain': 'Build Python services.',
				}
			]
		)
		adapter = LeverAdapter(
			company_slugs=['examplecoinc'],
			api_base_url=f'http://{server.host}:{server.port}',
		)
		postings = await adapter.fetch_all()

	assert len(postings) == 1
	posting = postings[0]
	assert posting.title == 'Senior Backend Engineer'
	assert posting.location == 'Remote'
	assert posting.ats_platform == 'lever'
	assert posting.jd_text == 'Build Python services.'
	assert posting.dedup_key == 'https://jobs.lever.co/examplecoinc/abc-123'
