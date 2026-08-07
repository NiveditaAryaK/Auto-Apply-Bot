from pydantic import BaseModel, ConfigDict

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage
from browser_use.llm.openai.chat import ChatOpenAI
from job_agent import config
from job_agent.resume.parse import parse_resume
from job_agent.resume.profile import ResumeProfile


class RoleProfile(BaseModel):
	model_config = ConfigDict(extra='forbid')

	role: str
	profile: ResumeProfile
	is_primary: bool


class _RoleLabel(BaseModel):
	model_config = ConfigDict(extra='forbid')

	role: str  # short free-text label, e.g. 'Backend Engineer' -- not chosen from any fixed list


async def _infer_role(profile: ResumeProfile, llm: BaseChatModel) -> str:
	"""Derive a short role/specialization label straight from the resume's own titles, summary,
	and skills, instead of requiring the user to hand-pick one from a fixed set of categories."""
	messages = [
		SystemMessage(
			content=(
				'Read this resume and produce a short (2-4 word) label for the role/specialization it '
				"targets, e.g. 'Backend Engineer' or 'Applied AI Engineer'. Base it only on the resume's "
				'own titles, summary, and skills -- do not pick from any predefined list of roles.'
			)
		),
		UserMessage(content=profile.model_dump_json(indent=2)),
	]
	result = await llm.ainvoke(messages, output_format=_RoleLabel)
	return result.completion.role


async def load_role_profiles(role_resumes: list[config.RoleResume], llm: BaseChatModel | None = None) -> list[RoleProfile]:
	"""Parse every configured resume and infer its role label from its own content. Requires
	exactly one is_primary=True entry -- hr_agent.route_and_screen falls back to it when a
	posting doesn't clearly match any inferred role."""
	primary_count = sum(1 for role_resume in role_resumes if role_resume.is_primary)
	if primary_count != 1:
		raise ValueError(
			f'Expected exactly one primary entry in config.ROLE_RESUMES, found {primary_count}. '
			'Set is_primary=True on exactly one RoleResume.'
		)

	llm = llm or ChatOpenAI(model=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

	role_profiles = []
	for role_resume in role_resumes:
		profile = await parse_resume(role_resume.resume_path, llm=llm)
		role = await _infer_role(profile, llm)
		role_profiles.append(RoleProfile(role=role, profile=profile, is_primary=role_resume.is_primary))
	return role_profiles


def primary_role_profile(role_profiles: list[RoleProfile]) -> RoleProfile:
	return next(rp for rp in role_profiles if rp.is_primary)
