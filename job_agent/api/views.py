from pydantic import BaseModel, ConfigDict


class ResumeOut(BaseModel):
	model_config = ConfigDict(extra='forbid')

	id: int
	filename: str
	is_primary: bool
	uploaded_at: str


class ApplicationOut(BaseModel):
	model_config = ConfigDict(extra='forbid')

	id: int
	dedup_key: str
	company: str
	title: str
	url: str
	ats_platform: str
	match_score: int | None
	match_reasoning: str | None
	resume_path: str | None
	status: str
	notes: str | None
	applied_at: str | None


class RunOut(BaseModel):
	model_config = ConfigDict(extra='forbid')

	id: int
	started_at: str
	finished_at: str | None
	status: str
	postings_found: int | None
	screened_pass: int | None
	screened_reject: int | None
	applied_count: int | None
	error: str | None


class ErrorOut(BaseModel):
	model_config = ConfigDict(extra='forbid')

	detail: str
