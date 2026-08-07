from browser_use.llm.base import BaseChatModel
from browser_use.llm.openai.chat import ChatOpenAI
from job_agent import config, db
from job_agent.discovery.base import JobPosting
from job_agent.discovery.search_agent import find_new_postings
from job_agent.hr_agent import RoleScreeningResult, route_and_screen
from job_agent.resume.roles import load_role_profiles


async def screen_new_postings(llm: BaseChatModel | None = None) -> list[tuple[JobPosting, RoleScreeningResult]]:
	"""End-to-end pipeline through HR Agent: load every configured resume (inferring its role from
	its own content), poll job boards for new keyword-matching postings via the web search agent,
	and screen each posting against whichever resume best fits it. Records every screening in
	db.applications (status 'screened_pass'/'screened_reject') so a later apply step can just
	query for passing rows instead of re-screening. Does not apply to anything -- that's the
	still-unbuilt Browser-Use step."""
	llm = llm or ChatOpenAI(model=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

	role_profiles = await load_role_profiles(config.ROLE_RESUMES, llm=llm)
	new_postings = await find_new_postings()

	results = []
	for posting in new_postings:
		result = await route_and_screen(role_profiles, posting, llm=llm)
		await db.record_application(
			dedup_key=posting.dedup_key,
			company=posting.company,
			title=posting.title,
			url=posting.url,
			ats_platform=posting.ats_platform,
			status='screened_pass' if result.screening.passes_screening else 'screened_reject',
			match_score=result.screening.match_score,
			match_reasoning=result.screening.reasoning,
			notes=f'role={result.role!r} used_fallback={result.used_fallback}',
		)
		results.append((posting, result))
	return results
