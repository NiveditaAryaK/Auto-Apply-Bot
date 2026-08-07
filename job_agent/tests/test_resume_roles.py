from pathlib import Path
from types import SimpleNamespace

import pytest

from job_agent import config
from job_agent.resume import roles as roles_module
from job_agent.resume.profile import ResumeProfile
from job_agent.resume.roles import load_role_profiles, primary_role_profile


def _fixture_resume_profile(summary: str) -> ResumeProfile:
	return ResumeProfile(
		full_name='Jane Doe', email='x@example.com', summary=summary, experience=[], projects=[], skills=[], education=[]
	)


class _FakeRoleInferenceLLM:
	"""Returns role labels in call order -- load_role_profiles infers one role per resume,
	sequentially, so the Nth ainvoke call corresponds to the Nth configured resume."""

	def __init__(self, role_labels: list[str]):
		self._role_labels = iter(role_labels)

	async def ainvoke(self, *_args, **_kwargs):
		return SimpleNamespace(completion=SimpleNamespace(role=next(self._role_labels)))


async def test_load_role_profiles_infers_role_from_each_resumes_own_content(monkeypatch):
	profiles_by_path = {
		Path('backend.pdf'): _fixture_resume_profile('Backend engineer, Python, Postgres.'),
		Path('applied_ai.pdf'): _fixture_resume_profile('Applied AI engineer, LLMs, PyTorch.'),
	}

	async def fake_parse_resume(path, llm=None):
		return profiles_by_path[path]

	monkeypatch.setattr(roles_module, 'parse_resume', fake_parse_resume)

	role_resumes = [
		config.RoleResume(resume_path=Path('backend.pdf'), is_primary=True),
		config.RoleResume(resume_path=Path('applied_ai.pdf')),
	]
	fake_llm = _FakeRoleInferenceLLM(['Backend Engineer', 'Applied AI Engineer'])

	role_profiles = await load_role_profiles(role_resumes, llm=fake_llm)

	# roles came from the LLM reading each resume's own content, not from a fixed list.
	assert [rp.role for rp in role_profiles] == ['Backend Engineer', 'Applied AI Engineer']
	assert role_profiles[0].is_primary is True
	assert role_profiles[1].is_primary is False
	assert primary_role_profile(role_profiles).role == 'Backend Engineer'


async def test_load_role_profiles_requires_exactly_one_primary():
	role_resumes = [
		config.RoleResume(resume_path=Path('backend.pdf')),
		config.RoleResume(resume_path=Path('applied_ai.pdf')),
	]

	with pytest.raises(ValueError, match='exactly one primary'):
		await load_role_profiles(role_resumes)


async def test_load_role_profiles_rejects_two_primaries():
	role_resumes = [
		config.RoleResume(resume_path=Path('backend.pdf'), is_primary=True),
		config.RoleResume(resume_path=Path('applied_ai.pdf'), is_primary=True),
	]

	with pytest.raises(ValueError, match='exactly one primary'):
		await load_role_profiles(role_resumes)
