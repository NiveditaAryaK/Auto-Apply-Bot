from pydantic import BaseModel, ConfigDict

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage
from job_agent import config
from job_agent.discovery.base import JobPosting
from job_agent.resume.profile import ResumeProfile
from job_agent.resume.roles import RoleProfile, primary_role_profile


class ScreeningResult(BaseModel):
	model_config = ConfigDict(extra='forbid')

	match_score: int  # 0-100
	reasoning: str

	@property
	def passes_screening(self) -> bool:
		return self.match_score >= config.MATCH_SCORE_THRESHOLD


async def screen_job(profile: ResumeProfile, posting: JobPosting, llm: BaseChatModel) -> ScreeningResult:
	"""Score how well the resume matches a job description the way an ATS keyword filter and a
	first-pass human recruiter would, so the apply step can skip postings that would just get
	auto-rejected. This runs after discovery/keyword filtering and before resume/selector.py --
	it decides *whether* to apply, selector decides *how* to tailor the resume once we do."""
	messages = [
		SystemMessage(
			content=(
				'You are an ATS/HR screener. Score how well the candidate resume matches the job '
				'description on a 0-100 scale, the way an applicant tracking system and a first-pass '
				'human recruiter would: keyword/skill overlap, years of experience against any stated '
				'requirement, and seniority/title fit. Be a harsh, realistic grader -- most applicants '
				'do not score above 80.'
			)
		),
		UserMessage(
			content=(
				f'Job title: {posting.title}\nCompany: {posting.company}\n\n'
				f'Job description:\n{posting.jd_text}\n\n'
				f'Candidate resume:\n{profile.model_dump_json(indent=2)}'
			)
		),
	]
	result = await llm.ainvoke(messages, output_format=ScreeningResult)
	screening = result.completion
	return ScreeningResult(match_score=max(0, min(100, screening.match_score)), reasoning=screening.reasoning)


class RoleMatch(BaseModel):
	model_config = ConfigDict(extra='forbid')

	role: str | None  # None if no inferred role is a clear fit -- caller falls back to primary
	reasoning: str


class RoleScreeningResult(BaseModel):
	model_config = ConfigDict(extra='forbid')

	role: str
	used_fallback: bool
	screening: ScreeningResult


async def _select_role(role_profiles: list[RoleProfile], posting: JobPosting, llm: BaseChatModel) -> RoleMatch:
	role_summaries = {rp.role: rp.profile.summary for rp in role_profiles}
	messages = [
		SystemMessage(
			content=(
				'The candidate has multiple resumes, each written for a different role/specialization '
				'(the role labels below were inferred from each resume, not chosen from a fixed list). '
				'Given a job posting, pick which role its resume is the best fit for. If none of the '
				'available roles are a clear fit, return null for role rather than guessing.'
			)
		),
		UserMessage(
			content=(
				f'Job title: {posting.title}\nJob description:\n{posting.jd_text}\n\n'
				f'Available roles and their resume summaries:\n{role_summaries}'
			)
		),
	]
	result = await llm.ainvoke(messages, output_format=RoleMatch)
	return result.completion


async def route_and_screen(role_profiles: list[RoleProfile], posting: JobPosting, llm: BaseChatModel) -> RoleScreeningResult:
	"""Pick which of the candidate's role-tagged resumes best fits this posting, then screen that
	resume against the JD. Discovery runs a single broad search across all roles (see
	config.KEYWORDS), so this is what actually maps a posting found by that search to the right
	resume. Falls back to the primary resume (config.RoleResume.is_primary) when the LLM can't
	confidently place the posting under any configured role, rather than dropping it."""
	if len(role_profiles) == 1:
		chosen_role_profile = role_profiles[0]
		used_fallback = False
	else:
		profile_by_role = {rp.role: rp for rp in role_profiles}
		match = await _select_role(role_profiles, posting, llm)
		chosen_role_profile = profile_by_role.get(match.role) if match.role else None
		used_fallback = chosen_role_profile is None
		chosen_role_profile = chosen_role_profile or primary_role_profile(role_profiles)

	screening = await screen_job(chosen_role_profile.profile, posting, llm)
	return RoleScreeningResult(role=chosen_role_profile.role, used_fallback=used_fallback, screening=screening)
