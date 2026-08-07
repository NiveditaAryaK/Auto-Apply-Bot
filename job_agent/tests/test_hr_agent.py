from types import SimpleNamespace

import pytest

from job_agent import config
from job_agent.discovery.base import JobPosting
from job_agent.hr_agent import RoleMatch, ScreeningResult, route_and_screen, screen_job
from job_agent.resume.profile import ResumeProfile
from job_agent.resume.roles import RoleProfile


def _fixture_profile(summary: str = 'Backend engineer.') -> ResumeProfile:
	return ResumeProfile(
		full_name='Jane Doe',
		email='jane@example.com',
		summary=summary,
		experience=[],
		projects=[],
		skills=[],
		education=[],
	)


def _fixture_role_profiles() -> list[RoleProfile]:
	# role labels here stand in for whatever resume/roles.py._infer_role would have derived from
	# each resume's own content -- arbitrary free text, not a fixed set of categories.
	return [
		RoleProfile(role='Backend Engineer', profile=_fixture_profile('Backend engineer.'), is_primary=True),
		RoleProfile(role='Applied AI Engineer', profile=_fixture_profile('Applied AI engineer.'), is_primary=False),
	]


def _fixture_posting() -> JobPosting:
	return JobPosting(
		company='Acme',
		title='Backend Engineer',
		url='https://boards.greenhouse.io/acme/jobs/1',
		ats_platform='greenhouse',
		jd_text='5+ years Python, distributed systems.',
	)


class _FakeLLM:
	def __init__(self, completion: ScreeningResult):
		self._completion = completion

	async def ainvoke(self, *_args, **_kwargs):
		return SimpleNamespace(completion=self._completion)


async def test_screen_job_returns_llm_score_and_reasoning():
	fake_llm = _FakeLLM(ScreeningResult(match_score=72, reasoning='Solid overlap.'))

	result = await screen_job(_fixture_profile(), _fixture_posting(), llm=fake_llm)

	assert result.match_score == 72
	assert result.reasoning == 'Solid overlap.'


@pytest.mark.parametrize(('raw_score', 'clamped_score'), [(150, 100), (-10, 0)])
async def test_screen_job_clamps_out_of_range_score(raw_score, clamped_score):
	fake_llm = _FakeLLM(ScreeningResult(match_score=raw_score, reasoning='n/a'))

	result = await screen_job(_fixture_profile(), _fixture_posting(), llm=fake_llm)

	assert result.match_score == clamped_score


def test_passes_screening_uses_configured_threshold(monkeypatch):
	monkeypatch.setattr(config, 'MATCH_SCORE_THRESHOLD', 80)

	assert ScreeningResult(match_score=80, reasoning='n/a').passes_screening is True
	assert ScreeningResult(match_score=79, reasoning='n/a').passes_screening is False


class _CountingScreeningLLM:
	"""Only ever asked to screen (not route) -- used to prove routing is skipped for a single resume."""

	def __init__(self, screening: ScreeningResult):
		self._screening = screening
		self.calls = 0

	async def ainvoke(self, _messages, output_format=None, **_kwargs):
		self.calls += 1
		assert output_format is ScreeningResult
		return SimpleNamespace(completion=self._screening)


class _RoutingFakeLLM:
	def __init__(self, role_match: RoleMatch, screening: ScreeningResult):
		self._role_match = role_match
		self._screening = screening

	async def ainvoke(self, _messages, output_format=None, **_kwargs):
		completion = self._role_match if output_format is RoleMatch else self._screening
		return SimpleNamespace(completion=completion)


async def test_route_and_screen_skips_routing_call_for_a_single_resume():
	role_profiles = _fixture_role_profiles()[:1]
	fake_llm = _CountingScreeningLLM(ScreeningResult(match_score=90, reasoning='n/a'))

	result = await route_and_screen(role_profiles, _fixture_posting(), llm=fake_llm)

	assert fake_llm.calls == 1
	assert result.role == role_profiles[0].role
	assert result.used_fallback is False


async def test_route_and_screen_uses_llm_selected_role():
	role_profiles = _fixture_role_profiles()
	fake_llm = _RoutingFakeLLM(
		role_match=RoleMatch(role='Applied AI Engineer', reasoning='LLM-heavy posting.'),
		screening=ScreeningResult(match_score=85, reasoning='n/a'),
	)

	result = await route_and_screen(role_profiles, _fixture_posting(), llm=fake_llm)

	assert result.role == 'Applied AI Engineer'
	assert result.used_fallback is False


async def test_route_and_screen_falls_back_to_primary_when_llm_finds_no_clear_fit():
	role_profiles = _fixture_role_profiles()
	fake_llm = _RoutingFakeLLM(
		role_match=RoleMatch(role=None, reasoning='Neither resume is a clear fit.'),
		screening=ScreeningResult(match_score=40, reasoning='n/a'),
	)

	result = await route_and_screen(role_profiles, _fixture_posting(), llm=fake_llm)

	primary_role = next(rp.role for rp in role_profiles if rp.is_primary)
	assert result.role == primary_role
	assert result.used_fallback is True


async def test_route_and_screen_falls_back_to_primary_when_llm_hallucinates_a_role():
	role_profiles = _fixture_role_profiles()
	fake_llm = _RoutingFakeLLM(
		role_match=RoleMatch(role='role-that-does-not-exist', reasoning='n/a'),
		screening=ScreeningResult(match_score=40, reasoning='n/a'),
	)

	result = await route_and_screen(role_profiles, _fixture_posting(), llm=fake_llm)

	primary_role = next(rp.role for rp in role_profiles if rp.is_primary)
	assert result.role == primary_role
	assert result.used_fallback is True
