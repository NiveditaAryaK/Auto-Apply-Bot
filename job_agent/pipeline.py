from collections.abc import Awaitable, Callable

from browser_use.llm.base import BaseChatModel
from browser_use.llm.openai.chat import ChatOpenAI
from job_agent import config, db
from job_agent.apply_agent import ApplicationOutcome, apply_to_posting
from job_agent.discovery.base import JobPosting
from job_agent.discovery.search_agent import find_new_postings
from job_agent.hr_agent import RoleScreeningResult, route_and_screen
from job_agent.resume.roles import RoleProfile, load_role_profiles

ProgressCallback = Callable[[str], Awaitable[None]]


async def _noop_progress(message: str) -> None:
	return None


async def screen_new_postings(
	llm: BaseChatModel | None = None,
	role_resumes: list[config.RoleResume] | None = None,
	on_progress: ProgressCallback | None = None,
) -> tuple[list[RoleProfile], list[tuple[JobPosting, RoleScreeningResult]]]:
	"""Web search agent + HR Agent: load every configured resume (inferring its role from its own
	content), poll job boards for new keyword-matching postings, and screen each posting against
	whichever resume best fits it. Records every screening in db.applications
	(status 'screened_pass'/'screened_reject'). Returns the loaded role profiles alongside the
	results so a caller can apply to the passing ones without re-parsing/re-inferring resumes.

	role_resumes defaults to config.ROLE_RESUMES -- pass it explicitly to screen against
	dynamically uploaded resumes (e.g. job_agent/api/runner.py building the list from db.resumes)
	instead of the static config list.

	on_progress, if given, is awaited with a short human-readable status string at each stage --
	job_agent/api/runner.py uses it to publish live progress onto the runs row so the web UI can
	show what a run is doing instead of just "running" for its whole duration."""
	llm = llm or ChatOpenAI(model=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
	role_resumes = role_resumes if role_resumes is not None else config.ROLE_RESUMES
	progress = on_progress or _noop_progress

	await progress('Loading resumes and inferring roles...')
	role_profiles = await load_role_profiles(role_resumes, llm=llm)

	await progress('Searching job boards for new postings...')
	new_postings = await find_new_postings()
	await progress(f'Found {len(new_postings)} new posting(s) -- screening...' if new_postings else 'No new postings found.')

	results = []
	for i, posting in enumerate(new_postings, start=1):
		await progress(f'Screening {i}/{len(new_postings)}: {posting.title} at {posting.company}')
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
	on_progress: ProgressCallback | None = None,
) -> list[ApplicationOutcome]:
	"""Browser-Use apply step: for every screened posting that passed, submit an application
	using whichever resume hr_agent.route_and_screen chose for it. Skips postings that didn't
	pass -- apply_agent.apply_to_posting is never called for a 'screened_reject' row."""
	llm = llm or ChatOpenAI(model=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
	progress = on_progress or _noop_progress
	profile_by_role = {rp.role: rp for rp in role_profiles}

	passing = [(posting, result) for posting, result in screened if result.screening.passes_screening]
	if not passing:
		await progress('No postings passed screening -- nothing to apply to.')
		return []

	outcomes = []
	for i, (posting, result) in enumerate(passing, start=1):
		await progress(f'Applying {i}/{len(passing)}: {posting.title} at {posting.company}')
		outcomes.append(await apply_to_posting(posting, profile_by_role[result.role], llm=llm))
	return outcomes


async def run(
	llm: BaseChatModel | None = None,
	role_resumes: list[config.RoleResume] | None = None,
	on_progress: ProgressCallback | None = None,
) -> list[ApplicationOutcome]:
	"""Full pipeline: Web Search Agent -> HR Agent -> Browser-Use apply step."""
	llm = llm or ChatOpenAI(model=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
	role_profiles, screened = await screen_new_postings(llm=llm, role_resumes=role_resumes, on_progress=on_progress)
	outcomes = await apply_to_passing_postings(role_profiles, screened, llm=llm, on_progress=on_progress)
	await (on_progress or _noop_progress)('Done.')
	return outcomes
