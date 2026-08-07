import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

from browser_use import Agent
from browser_use.llm.base import BaseChatModel
from browser_use.llm.openai.chat import ChatOpenAI
from job_agent import config, db
from job_agent.discovery.base import JobPosting
from job_agent.resume.render import render_resume
from job_agent.resume.roles import RoleProfile
from job_agent.resume.selector import select_blocks


class ApplicationOutcome(BaseModel):
	model_config = ConfigDict(extra='forbid')

	submitted: bool
	questions_encountered: list[str]  # form questions the agent couldn't answer from the resume


def _resume_filename(posting: JobPosting) -> str:
	slug = re.sub(r'[^a-z0-9]+', '-', f'{posting.company}-{posting.title}'.lower()).strip('-')
	url_hash = hashlib.sha1(posting.url.encode()).hexdigest()[:8]
	return f'{slug}-{url_hash}.pdf'


def _apply_task_prompt(posting: JobPosting, role_profile: RoleProfile, resume_path: Path) -> str:
	profile = role_profile.profile
	contact_info = {
		'full_name': profile.full_name,
		'email': profile.email,
		'phone': profile.phone,
		'location': profile.location,
	}
	return (
		f'Apply to the "{posting.title}" role at {posting.company}, posted at {posting.url}.\n\n'
		f'Candidate contact info (use exactly as given, never invent alternatives): {contact_info}\n'
		f'Candidate summary: {profile.summary}\n\n'
		'- Navigate to the posting URL and open its application form.\n'
		f'- Upload the resume at {resume_path} wherever a resume/CV upload field appears.\n'
		'- Fill out every required field using the contact info above and anything else visible '
		'on the page. If a field asks something neither the contact info nor the page answers, '
		'make a reasonable, conservative guess -- but never fabricate work authorization, '
		'sponsorship, or salary figures; skip those and add the exact question text to '
		'questions_encountered instead.\n'
		'- Submit the application and confirm a success/confirmation screen appears before '
		'calling done.\n'
		'- If anything blocks the form (cookie banner, modal), close it and continue.'
	)


async def _rate_limit_allows(url: str) -> bool:
	"""Per-domain apply throttle (config.RATE_LIMITS): counts this hour's successful applies to
	the same domain and refuses once the configured cap is hit, so we don't hammer an ATS/job
	board and get the account flagged."""
	domain = urlparse(url).netloc
	max_per_hour = config.RATE_LIMITS.get(domain, config.RATE_LIMITS['default'])
	since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
	recent_urls = await db.get_recent_applied_urls(since)
	applied_this_hour = sum(1 for recent_url in recent_urls if urlparse(recent_url).netloc == domain)
	return applied_this_hour < max_per_hour


async def _run_apply_agent(posting: JobPosting, role_profile: RoleProfile, resume_path: Path, llm: BaseChatModel) -> ApplicationOutcome:
	"""Drive an actual browser-use Agent through the application form. Split out from
	apply_to_posting so tests can stub this one call without launching a real browser."""
	agent = Agent(
		task=_apply_task_prompt(posting, role_profile, resume_path),
		llm=llm,
		available_file_paths=[str(resume_path)],
		output_model_schema=ApplicationOutcome,
	)
	history = await agent.run(max_steps=config.APPLY_MAX_STEPS)
	if history.structured_output is not None:
		return history.structured_output
	return ApplicationOutcome(submitted=bool(history.is_successful()), questions_encountered=[])


async def apply_to_posting(posting: JobPosting, role_profile: RoleProfile, llm: BaseChatModel | None = None) -> ApplicationOutcome:
	"""Tailor a resume for this posting and submit it through the actual application form via
	browser-use. Callers should only invoke this for postings already screened as a pass
	(hr_agent.ScreeningResult.passes_screening); this function itself only enforces the
	per-domain rate limit and records the outcome to db.applications."""
	if not await _rate_limit_allows(posting.url):
		await db.record_application(
			dedup_key=posting.dedup_key,
			company=posting.company,
			title=posting.title,
			url=posting.url,
			ats_platform=posting.ats_platform,
			status='rate_limited',
		)
		return ApplicationOutcome(submitted=False, questions_encountered=[])

	llm = llm or ChatOpenAI(model=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

	selection = await select_blocks(role_profile.profile, posting.jd_text, llm)
	resume_path = render_resume(role_profile.profile, selection, config.RESUME_OUTPUT_DIR / _resume_filename(posting))

	outcome = await _run_apply_agent(posting, role_profile, resume_path, llm)

	await db.record_application(
		dedup_key=posting.dedup_key,
		company=posting.company,
		title=posting.title,
		url=posting.url,
		ats_platform=posting.ats_platform,
		status='applied' if outcome.submitted else 'apply_failed',
		resume_path=str(resume_path),
		notes='; '.join(outcome.questions_encountered) or None,
	)
	return outcome
