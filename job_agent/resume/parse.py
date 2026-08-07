from pathlib import Path

from pydantic import BaseModel, ConfigDict

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage
from browser_use.llm.openai.chat import ChatOpenAI
from job_agent import config
from job_agent.resume.profile import EducationEntry, ExperienceBlock, ProjectBlock, ResumeProfile, SkillGroup

_NO_INVENT_INSTRUCTION = (
	'Copy content verbatim (or lightly cleaned up for whitespace/OCR artifacts) from the source '
	'resume text below -- do not invent, embellish, or add anything not explicitly present.'
)


class _ContactAndSummary(BaseModel):
	model_config = ConfigDict(extra='forbid')

	full_name: str
	email: str
	phone: str | None = None
	location: str | None = None
	summary: str


class _ExperienceList(BaseModel):
	model_config = ConfigDict(extra='forbid')

	experience: list[ExperienceBlock]


class _ProjectList(BaseModel):
	model_config = ConfigDict(extra='forbid')

	projects: list[ProjectBlock]


class _SkillsAndEducation(BaseModel):
	model_config = ConfigDict(extra='forbid')

	skills: list[SkillGroup]
	education: list[EducationEntry]


def _extract_text(path: Path) -> str:
	suffix = path.suffix.lower()
	if suffix == '.pdf':
		import pypdf

		reader = pypdf.PdfReader(str(path))
		return '\n'.join(page.extract_text() or '' for page in reader.pages)
	elif suffix == '.docx':
		import docx

		document = docx.Document(str(path))
		return '\n'.join(paragraph.text for paragraph in document.paragraphs)
	else:
		raise ValueError(f'Unsupported resume file type: {suffix!r}, expected .pdf or .docx')


async def parse_resume(path: Path, llm: BaseChatModel | None = None) -> ResumeProfile:
	"""One-time (or on-demand, whenever the master resume changes) conversion of a real
	PDF/DOCX resume into structured, selectable blocks. This is the only place resume content
	is allowed to originate from an LLM read of the source file -- resume/selector.py may only
	choose and reorder these blocks afterward, never invent new content.

	Split into four small, flat-schema calls rather than one large nested one: locally-served
	reasoning models (e.g. gpt-oss-20b via LM Studio) were observed to produce garbled output or
	stall on a single deeply-nested ResumeProfile extraction, while short flat-schema calls stay
	fast and reliable."""
	llm = llm or ChatOpenAI(model=config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
	raw_text = _extract_text(path)

	contact = await _extract(llm, raw_text, _ContactAndSummary, 'the candidate\'s name, contact info, and summary')
	experience = await _extract(llm, raw_text, _ExperienceList, "each work experience entry, with a stable id like 'exp-1'")
	projects = await _extract(
		llm,
		raw_text,
		_ProjectList,
		"each entry listed under a distinct 'Projects' (or 'Personal Projects') section only, with a "
		"stable id like 'proj-1'. Do not duplicate or re-list anything already covered under Experience "
		'-- if there is no separate Projects section, return an empty list',
	)
	skills_and_education = await _extract(
		llm, raw_text, _SkillsAndEducation, "skill groups (stable id like 'skill-1') and education entries"
	)

	return ResumeProfile(
		full_name=contact.full_name,
		email=contact.email,
		phone=contact.phone,
		location=contact.location,
		summary=contact.summary,
		experience=experience.experience,
		projects=projects.projects,
		skills=skills_and_education.skills,
		education=skills_and_education.education,
	)


async def _extract(llm: BaseChatModel, raw_text: str, output_format: type, what: str):
	messages = [
		SystemMessage(content=f'Extract {what} from this resume. {_NO_INVENT_INSTRUCTION}'),
		UserMessage(content=raw_text),
	]
	result = await llm.ainvoke(messages, output_format=output_format)
	return result.completion
