from pydantic import BaseModel, ConfigDict

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage
from job_agent import config
from job_agent.discovery.base import JobPosting
from job_agent.resume.profile import ResumeProfile


class ScreeningResult(BaseModel):
	model_config = ConfigDict(extra='forbid')

	match_score: int  # 0-100
	reasoning: str
	missing_keywords: list[str]

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
				'requirement, and seniority/title fit. List any requirement keywords from the JD that '
				'the resume shows no evidence of meeting. Be a harsh, realistic grader -- most '
				'applicants do not score above 80.'
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
	return ScreeningResult(
		match_score=max(0, min(100, screening.match_score)),
		reasoning=screening.reasoning,
		missing_keywords=screening.missing_keywords,
	)
