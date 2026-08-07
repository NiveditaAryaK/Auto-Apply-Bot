from pydantic import BaseModel, ConfigDict


class ExperienceBlock(BaseModel):
	model_config = ConfigDict(extra='forbid')

	id: str
	company: str
	title: str
	start_date: str
	end_date: str | None = None  # None means current role
	bullets: list[str]


class ProjectBlock(BaseModel):
	model_config = ConfigDict(extra='forbid')

	id: str
	name: str
	description: str
	bullets: list[str]


class SkillGroup(BaseModel):
	model_config = ConfigDict(extra='forbid')

	id: str
	category: str
	skills: list[str]


class EducationEntry(BaseModel):
	model_config = ConfigDict(extra='forbid')

	school: str
	degree: str
	end_date: str | None = None


class ResumeProfile(BaseModel):
	model_config = ConfigDict(extra='forbid')

	full_name: str
	email: str
	phone: str | None = None
	location: str | None = None
	summary: str
	experience: list[ExperienceBlock]
	projects: list[ProjectBlock]
	skills: list[SkillGroup]
	education: list[EducationEntry]
