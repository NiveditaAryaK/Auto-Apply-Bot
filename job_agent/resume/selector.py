from pydantic import BaseModel, ConfigDict

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage
from job_agent.resume.profile import ResumeProfile


class BlockSelection(BaseModel):
	model_config = ConfigDict(extra='forbid')

	experience_ids: list[str]
	project_ids: list[str]
	skill_ids: list[str]


async def select_blocks(profile: ResumeProfile, jd_text: str, llm: BaseChatModel) -> BlockSelection:
	"""Ask the LLM which existing blocks to include/reorder for this JD -- selection only,
	never freeform rewriting. The result is validated against the profile's real block ids
	below: experience is always included in full (LLM only controls ordering), and any
	hallucinated/unknown id in any list is dropped rather than trusted."""
	available_ids = {
		'experience_ids': [e.id for e in profile.experience],
		'project_ids': [p.id for p in profile.projects],
		'skill_ids': [s.id for s in profile.skills],
	}
	messages = [
		SystemMessage(
			content=(
				'Given a job description and a candidate resume broken into blocks, choose which '
				'block ids to include and in what order for this specific application. Select only '
				'from the given available ids -- never invent new ids or content. Always return every '
				'experience id (reordered by relevance); projects and skill groups may be trimmed to '
				'the most relevant subset.'
			)
		),
		UserMessage(
			content=(
				f'Job description:\n{jd_text}\n\n'
				f'Available block ids:\n{available_ids}\n\n'
				f'Full resume for context:\n{profile.model_dump_json(indent=2)}'
			)
		),
	]
	result = await llm.ainvoke(messages, output_format=BlockSelection)
	selection = result.completion

	valid_experience_ids = set(available_ids['experience_ids'])
	valid_project_ids = set(available_ids['project_ids'])
	valid_skill_ids = set(available_ids['skill_ids'])

	ordered_experience_ids = [i for i in selection.experience_ids if i in valid_experience_ids]
	missing_experience_ids = [i for i in available_ids['experience_ids'] if i not in ordered_experience_ids]

	return BlockSelection(
		experience_ids=ordered_experience_ids + missing_experience_ids,
		project_ids=[i for i in selection.project_ids if i in valid_project_ids],
		skill_ids=[i for i in selection.skill_ids if i in valid_skill_ids],
	)
