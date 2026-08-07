from job_agent import config
from job_agent.discovery.base import JobPosting
from job_agent.discovery.search_agent import find_new_postings


def _posting(company: str, title: str, jd_text: str, url: str) -> JobPosting:
	return JobPosting(company=company, title=title, url=url, ats_platform='greenhouse', jd_text=jd_text)


class _FakeAdapter:
	ats_platform = 'greenhouse'

	def __init__(self, postings: list[JobPosting]):
		self._postings = postings

	async def fetch_all(self) -> list[JobPosting]:
		return self._postings


async def test_find_new_postings_filters_by_keywords_and_remaps_company_name():
	target_companies = [config.TargetCompany(name='Acme Inc', ats_platform='greenhouse', board_token='acme')]
	fake_adapter = _FakeAdapter(
		[
			_posting('acme', 'Backend Engineer', 'Python and Postgres.', 'https://boards.greenhouse.io/acme/jobs/1'),
			_posting('acme', 'Sales Rep', 'Quota carrying.', 'https://boards.greenhouse.io/acme/jobs/2'),
		]
	)

	postings = await find_new_postings(target_companies=target_companies, keywords=['python'], adapters=[fake_adapter])

	assert len(postings) == 1
	assert postings[0].title == 'Backend Engineer'
	assert postings[0].company == 'Acme Inc'  # remapped from the raw board token to the configured name


async def test_find_new_postings_dedupes_across_calls():
	target_companies = [config.TargetCompany(name='Acme Inc', ats_platform='greenhouse', board_token='acme')]
	fake_adapter = _FakeAdapter(
		[_posting('acme', 'Backend Engineer', 'Python.', 'https://boards.greenhouse.io/acme/jobs/1')]
	)

	first_run = await find_new_postings(target_companies=target_companies, keywords=[], adapters=[fake_adapter])
	second_run = await find_new_postings(target_companies=target_companies, keywords=[], adapters=[fake_adapter])

	assert len(first_run) == 1
	assert second_run == []
