import httpx

from job_agent.discovery.base import JobPosting


class LeverAdapter:
	"""Lever, like Greenhouse, has no cross-company keyword-search API -- this polls each
	company slug's full posting list and relies on filter_by_keywords() downstream."""

	ats_platform = 'lever'

	def __init__(self, company_slugs: list[str], api_base_url: str = 'https://api.lever.co'):
		self.company_slugs = company_slugs
		self.api_base_url = api_base_url

	async def fetch_all(self) -> list[JobPosting]:
		postings: list[JobPosting] = []
		async with httpx.AsyncClient(timeout=30.0) as client:
			for slug in self.company_slugs:
				response = await client.get(
					f'{self.api_base_url}/v0/postings/{slug}',
					params={'mode': 'json'},
				)
				response.raise_for_status()
				for job in response.json():
					categories = job.get('categories') or {}
					postings.append(
						JobPosting(
							company=slug,
							title=job['text'],
							location=categories.get('location'),
							url=job['hostedUrl'],
							ats_platform=self.ats_platform,
							jd_text=job.get('descriptionPlain') or job.get('description') or '',
						)
					)
		return postings
