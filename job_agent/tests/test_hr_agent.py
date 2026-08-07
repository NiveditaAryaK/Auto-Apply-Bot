from types import SimpleNamespace

import pytest

from job_agent import config
from job_agent.discovery.base import JobPosting
from job_agent.hr_agent import ScreeningResult, screen_job
from job_agent.resume.profile import ResumeProfile


def _fixture_profile() -> ResumeProfile:
	return ResumeProfile(
		full_name='Jane Doe',
		email='jane@example.com',
		summary='Backend engineer.',
		experience=[],
		projects=[],
		skills=[],
		education=[],
	)


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
	fake_llm = _FakeLLM(ScreeningResult(match_score=72, reasoning='Solid overlap.', missing_keywords=['Kubernetes']))

	result = await screen_job(_fixture_profile(), _fixture_posting(), llm=fake_llm)

	assert result.match_score == 72
	assert result.reasoning == 'Solid overlap.'
	assert result.missing_keywords == ['Kubernetes']


@pytest.mark.parametrize(('raw_score', 'clamped_score'), [(150, 100), (-10, 0)])
async def test_screen_job_clamps_out_of_range_score(raw_score, clamped_score):
	fake_llm = _FakeLLM(ScreeningResult(match_score=raw_score, reasoning='n/a', missing_keywords=[]))

	result = await screen_job(_fixture_profile(), _fixture_posting(), llm=fake_llm)

	assert result.match_score == clamped_score


def test_passes_screening_uses_configured_threshold(monkeypatch):
	monkeypatch.setattr(config, 'MATCH_SCORE_THRESHOLD', 80)

	assert ScreeningResult(match_score=80, reasoning='n/a', missing_keywords=[]).passes_screening is True
	assert ScreeningResult(match_score=79, reasoning='n/a', missing_keywords=[]).passes_screening is False
