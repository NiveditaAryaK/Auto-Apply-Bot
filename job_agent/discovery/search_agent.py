from job_agent import config, db
from job_agent.discovery.base import DiscoveryAdapter, JobPosting, filter_by_keywords
from job_agent.discovery.greenhouse import GreenhouseAdapter
from job_agent.discovery.lever import LeverAdapter


def _build_adapters(target_companies: list[config.TargetCompany]) -> list[DiscoveryAdapter]:
	"""Group target companies by ATS platform so each adapter is queried once with every one of
	its board tokens/slugs, rather than opening one httpx client per company."""
	greenhouse_tokens = [tc.board_token for tc in target_companies if tc.ats_platform == 'greenhouse']
	lever_slugs = [tc.board_token for tc in target_companies if tc.ats_platform == 'lever']

	adapters: list[DiscoveryAdapter] = []
	if greenhouse_tokens:
		adapters.append(GreenhouseAdapter(board_tokens=greenhouse_tokens))
	if lever_slugs:
		adapters.append(LeverAdapter(company_slugs=lever_slugs))
	return adapters


async def find_new_postings(
	target_companies: list[config.TargetCompany] | None = None,
	keywords: list[str] | None = None,
	adapters: list[DiscoveryAdapter] | None = None,
) -> list[JobPosting]:
	"""Poll every configured company board, keep only postings mentioning a configured keyword,
	and drop any already recorded in db.seen_jobs from a previous run. Marks every kept posting
	seen so a later run of this same function doesn't re-surface it. `adapters` defaults to one
	built from `target_companies` -- pass it explicitly to inject fakes/test doubles."""
	target_companies = config.TARGET_COMPANIES if target_companies is None else target_companies
	keywords = config.KEYWORDS if keywords is None else keywords
	adapters = _build_adapters(target_companies) if adapters is None else adapters
	name_by_token = {tc.board_token: tc.name for tc in target_companies}

	all_postings: list[JobPosting] = []
	for adapter in adapters:
		for posting in await adapter.fetch_all():
			# adapters report the raw board token/slug as `company` -- swap in the human-readable
			# name configured in config.TARGET_COMPANIES wherever we have one.
			company_name = name_by_token.get(posting.company, posting.company)
			all_postings.append(posting.model_copy(update={'company': company_name}))

	new_postings = []
	for posting in filter_by_keywords(all_postings, keywords):
		if await db.is_seen(posting.dedup_key):
			continue
		await db.mark_seen(posting.dedup_key, posting.company, posting.title, posting.url, posting.ats_platform)
		new_postings.append(posting)
	return new_postings
