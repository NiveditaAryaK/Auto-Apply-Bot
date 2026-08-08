from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class JobPosting(BaseModel):
	model_config = ConfigDict(extra='forbid')

	company: str
	title: str
	location: str | None = None
	url: str
	ats_platform: str
	jd_text: str
	posted_at: datetime | None = None

	@property
	def dedup_key(self) -> str:
		return self.url.split('?')[0].rstrip('/')


class DiscoveryAdapter(Protocol):
	ats_platform: str

	async def fetch_all(self) -> list[JobPosting]: ...


def filter_by_keywords(postings: list[JobPosting], keywords: list[str]) -> list[JobPosting]:
	"""Keep only postings whose title or JD mentions at least one keyword (case-insensitive).
	An empty keyword list matches everything -- treat it as 'no filter configured' rather than
	'match nothing'."""
	if not keywords:
		return postings
	lowered_keywords = [k.lower() for k in keywords]
	return [
		posting
		for posting in postings
		if any(k in posting.title.lower() or k in posting.jd_text.lower() for k in lowered_keywords)
	]
