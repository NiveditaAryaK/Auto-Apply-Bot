from browser_use.llm.base import BaseChatModel
from browser_use.llm.openai.chat import ChatOpenAI
from job_agent import config, db
from job_agent.apply_agent import ApplicationOutcome, apply_to_posting
from job_agent.discovery.base import JobPosting
from job_agent.discovery.search_agent import find_new_postings
from job_agent.hr_agent import RoleScreeningResult, route_and_screen
from job_agent.resume.roles import RoleProfile, load_role_profiles


async def screen_new_postings(
	llm: BaseChatModel | None = None,
) -> tuple[list[RoleProfile], list[tuple[JobPosting, RoleScreeningResult]]]:
	"""Web search agent + HR Agent: load every configured resume (inferring its role from its own
	content), poll job boards for new keyword-matching postings, and screen each posting against
	whichever resume best fits it. Records every screening in db.applications
	(status 'screened_pass'/'screened_reject'). Returns the loaded role profiles alongside the
	results so a caller can apply to the passing ones without re-parsing/re-inferring resumes."""
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
	return role_profiles, results


async def apply_to_passing_postings(
	role_profiles: list[RoleProfile],
	screened: list[tuple[JobPosting, RoleScreeningResult]],
	llm: BaseChatModel | None = None,
) -> list[ApplicationOutcome]:
	"""Browser-Use apply step: for every screened posting that passed, submit an application
	using whichever resume hr_agent.route_and_screen chose for it. Skips postings that didn't
	pass -- apply_agent.apply_to_posting is never called for a 'screened_reject' row."""
	llm = llm or ChatOpenAI(model=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
	profile_by_role = {rp.role: rp for rp in role_profiles}

	outcomes = []
	for posting, result in screened:
		if not result.screening.passes_screening:
			continue
		outcomes.append(await apply_to_posting(posting, profile_by_role[result.role], llm=llm))
	return outcomes


async def run(llm: BaseChatModel | None = None) -> list[ApplicationOutcome]:
	"""Full pipeline: Web Search Agent -> HR Agent -> Browser-Use apply step."""
	llm = llm or ChatOpenAI(model=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
	role_profiles, screened = await screen_new_postings(llm=llm)
	return await apply_to_passing_postings(role_profiles, screened, llm=llm)
