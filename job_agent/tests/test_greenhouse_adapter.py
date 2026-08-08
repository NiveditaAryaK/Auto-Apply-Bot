from pytest_httpserver import HTTPServer

from job_agent.discovery.base import JobPosting, filter_by_keywords
from job_agent.discovery.greenhouse import GreenhouseAdapter


async def test_fetch_all_parses_jobs_and_converts_html_content():
	with HTTPServer() as server:
		server.expect_request('/v1/boards/examplecoinc/jobs', query_string='content=true').respond_with_json(
			{
				'jobs': [
					{
						'title': 'Senior Backend Engineer',
						'location': {'name': 'Remote'},
						'absolute_url': 'https://boards.greenhouse.io/examplecoinc/jobs/123?gh_src=abc',
						'content': '<p>Build <strong>Python</strong> services.</p>',
					}
				]
			}
		)
		adapter = GreenhouseAdapter(
			board_tokens=['examplecoinc'],
			api_base_url=f'http://{server.host}:{server.port}',
		)
		postings = await adapter.fetch_all()

	assert len(postings) == 1
	posting = postings[0]
	assert posting.title == 'Senior Backend Engineer'
	assert posting.location == 'Remote'
	assert posting.ats_platform == 'greenhouse'
	assert 'Python' in posting.jd_text
	assert posting.dedup_key == 'https://boards.greenhouse.io/examplecoinc/jobs/123'


def test_filter_by_keywords_matches_title_or_jd_case_insensitive():
	postings = [
		JobPosting(company='a', title='Backend Engineer', url='https://x/1', ats_platform='greenhouse', jd_text='Go and Rust'),
		JobPosting(company='b', title='Frontend Engineer', url='https://x/2', ats_platform='greenhouse', jd_text='React'),
	]
	assert [p.title for p in filter_by_keywords(postings, ['backend'])] == ['Backend Engineer']
	assert [p.title for p in filter_by_keywords(postings, [])] == ['Backend Engineer', 'Frontend Engineer']
