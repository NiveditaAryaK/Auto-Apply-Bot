from types import SimpleNamespace

from job_agent import apply_agent as apply_agent_module
from job_agent import config, db
from job_agent.apply_agent import ApplicationOutcome, apply_to_posting
from job_agent.discovery.base import JobPosting
from job_agent.resume.profile import ResumeProfile
from job_agent.resume.roles import RoleProfile
from job_agent.resume.selector import BlockSelection


def _fixture_role_profile() -> RoleProfile:
	profile = ResumeProfile(
		full_name='Jane Doe',
		email='jane@example.com',
		summary='Backend engineer.',
		experience=[],
		projects=[],
		skills=[],
		education=[],
	)
	return RoleProfile(role='Backend Engineer', profile=profile, is_primary=True)


def _fixture_posting() -> JobPosting:
	return JobPosting(
		company='Acme', title='Backend Engineer', url='https://boards.greenhouse.io/acme/jobs/1', ats_platform='greenhouse', jd_text='Python.'
	)


class _FakeSelectorLLM:
	"""Stands in for select_blocks()'s LLM call inside apply_to_posting -- returns an empty selection."""

	async def ainvoke(self, *_args, **_kwargs):
		return SimpleNamespace(completion=BlockSelection(experience_ids=[], project_ids=[], skill_ids=[]))


async def test_apply_to_posting_records_applied_status_and_renders_a_resume(monkeypatch):
	role_profile = _fixture_role_profile()
	posting = _fixture_posting()

	async def fake_run_apply_agent(posting_arg, role_profile_arg, resume_path, llm):
		assert posting_arg is posting
		assert resume_path.exists()  # render_resume already ran before this is called
		return ApplicationOutcome(submitted=True, questions_encountered=[])

	monkeypatch.setattr(apply_agent_module, '_run_apply_agent', fake_run_apply_agent)

	outcome = await apply_to_posting(posting, role_profile, llm=_FakeSelectorLLM())

	assert outcome.submitted is True
	application = await db.get_application(posting.dedup_key)
	assert application is not None
	assert application['status'] == 'applied'
	assert application['resume_path'] is not None


async def test_apply_to_posting_records_failed_status_with_unanswered_questions_in_notes(monkeypatch):
	role_profile = _fixture_role_profile()
	posting = _fixture_posting()

	async def fake_run_apply_agent(posting_arg, role_profile_arg, resume_path, llm):
		return ApplicationOutcome(submitted=False, questions_encountered=['Are you authorized to work in the US?'])

	monkeypatch.setattr(apply_agent_module, '_run_apply_agent', fake_run_apply_agent)

	outcome = await apply_to_posting(posting, role_profile, llm=_FakeSelectorLLM())

	assert outcome.submitted is False
	application = await db.get_application(posting.dedup_key)
	assert application is not None
	assert application['status'] == 'apply_failed'
	assert application['notes'] is not None
	assert 'authorized to work' in application['notes']


async def test_apply_to_posting_skips_the_browser_agent_when_domain_is_rate_limited(monkeypatch):
	role_profile = _fixture_role_profile()
	posting = _fixture_posting()
	monkeypatch.setitem(config.RATE_LIMITS, 'boards.greenhouse.io', 0)

	async def fail_if_called(*_args, **_kwargs):
		raise AssertionError('should not run the browser-use agent when rate-limited')

	monkeypatch.setattr(apply_agent_module, '_run_apply_agent', fail_if_called)

	outcome = await apply_to_posting(posting, role_profile, llm=_FakeSelectorLLM())

	assert outcome.submitted is False
	application = await db.get_application(posting.dedup_key)
	assert application is not None
	assert application['status'] == 'rate_limited'
