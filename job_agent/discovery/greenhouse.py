import httpx
from markdownify import markdownify as md

from job_agent.discovery.base import JobPosting


class GreenhouseAdapter:
	"""Greenhouse has no cross-company keyword-search API -- this polls each board token's
	full job list and relies on filter_by_keywords() downstream."""

	ats_platform = 'greenhouse'

	def __init__(self, board_tokens: list[str], api_base_url: str = 'https://boards-api.greenhouse.io'):
		self.board_tokens = board_tokens
		self.api_base_url = api_base_url

	async def fetch_all(self) -> list[JobPosting]:
		postings: list[JobPosting] = []
		async with httpx.AsyncClient(timeout=30.0) as client:
			for token in self.board_tokens:
				response = await client.get(
					f'{self.api_base_url}/v1/boards/{token}/jobs',
					params={'content': 'true'},
				)
				response.raise_for_status()
				for job in response.json().get('jobs', []):
					postings.append(
						JobPosting(
							company=token,
							title=job['title'],
							location=(job.get('location') or {}).get('name'),
							url=job['absolute_url'],
							ats_platform=self.ats_platform,
							jd_text=md(job.get('content') or ''),
						)
					)
		return postings
