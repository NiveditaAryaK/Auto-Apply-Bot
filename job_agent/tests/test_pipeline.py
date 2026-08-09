from pathlib import Path
from types import SimpleNamespace

from job_agent import config, db, pipeline
from job_agent.apply_agent import ApplicationOutcome
from job_agent.discovery.base import JobPosting
from job_agent.hr_agent import RoleScreeningResult, ScreeningResult
from job_agent.resume.profile import ResumeProfile
from job_agent.resume.roles import RoleProfile


def _fixture_role_profiles() -> list[RoleProfile]:
	profile = ResumeProfile(
		full_name='Jane Doe', email='jane@example.com', summary='Backend engineer.', experience=[], projects=[], skills=[], education=[]
	)
	return [RoleProfile(role='Backend Engineer', profile=profile, is_primary=True)]


def _fixture_posting() -> JobPosting:
	return JobPosting(
		company='Acme',
		title='Backend Engineer',
		url='https://boards.greenhouse.io/acme/jobs/1',
		ats_platform='greenhouse',
		jd_text='Python and Postgres.',
	)


def _patch_pipeline(monkeypatch, role_profiles, postings, screening_result):
	async def fake_load_role_profiles(role_resumes, llm=None):
		return role_profiles

	async def fake_find_new_postings():
		return postings

	async def fake_route_and_screen(profiles, posting, llm):
		assert profiles is role_profiles
		return screening_result

	monkeypatch.setattr(pipeline, 'load_role_profiles', fake_load_role_profiles)
	monkeypatch.setattr(pipeline, 'find_new_postings', fake_find_new_postings)
	monkeypatch.setattr(pipeline, 'route_and_screen', fake_route_and_screen)


async def test_screen_new_postings_records_a_passing_screening(monkeypatch):
	role_profiles = _fixture_role_profiles()
	posting = _fixture_posting()
	screening_result = RoleScreeningResult(
		role='Backend Engineer',
		used_fallback=False,
		screening=ScreeningResult(match_score=90, reasoning='Great fit.'),
	)
	_patch_pipeline(monkeypatch, role_profiles, [posting], screening_result)

	returned_role_profiles, results = await pipeline.screen_new_postings(llm=SimpleNamespace())

	assert returned_role_profiles == role_profiles
	assert results == [(posting, screening_result)]
	application = await db.get_application(posting.dedup_key)
	assert application is not None
	assert application['status'] == 'screened_pass'
	assert application['match_score'] == 90
	assert "role='Backend Engineer'" in application['notes']
	assert 'used_fallback=False' in application['notes']


async def test_screen_new_postings_records_a_failing_screening_as_rejected(monkeypatch):
	role_profiles = _fixture_role_profiles()
	posting = _fixture_posting()
	screening_result = RoleScreeningResult(
		role='Backend Engineer',
		used_fallback=True,
		screening=ScreeningResult(match_score=40, reasoning='Weak fit.'),
	)
	_patch_pipeline(monkeypatch, role_profiles, [posting], screening_result)

	await pipeline.screen_new_postings(llm=SimpleNamespace())

	application = await db.get_application(posting.dedup_key)
	assert application is not None
	assert application['status'] == 'screened_reject'
	assert application['match_score'] == 40


async def test_screen_new_postings_returns_empty_list_when_no_new_postings(monkeypatch):
	role_profiles = _fixture_role_profiles()
	_patch_pipeline(monkeypatch, role_profiles, [], screening_result=None)

	_, results = await pipeline.screen_new_postings(llm=SimpleNamespace())

	assert results == []


async def test_screen_new_postings_uses_injected_role_resumes_over_config(monkeypatch):
	"""role_resumes lets a caller (e.g. the API layer, building the list from db.resumes) screen
	against dynamically uploaded resumes instead of the static config.ROLE_RESUMES list."""
	role_profiles = _fixture_role_profiles()
	posting = _fixture_posting()
	screening_result = RoleScreeningResult(
		role='Backend Engineer', used_fallback=False, screening=ScreeningResult(match_score=90, reasoning='n/a')
	)
	_patch_pipeline(monkeypatch, role_profiles, [posting], screening_result)

	seen_role_resumes = []

	async def fake_load_role_profiles(role_resumes, llm=None):
		seen_role_resumes.append(role_resumes)
		return role_profiles

	monkeypatch.setattr(pipeline, 'load_role_profiles', fake_load_role_profiles)

	injected = [config.RoleResume(resume_path=Path('uploaded.pdf'), is_primary=True)]
	await pipeline.screen_new_postings(llm=SimpleNamespace(), role_resumes=injected)

	assert seen_role_resumes == [injected]


async def test_apply_to_passing_postings_skips_rejected_and_applies_to_passing(monkeypatch):
	role_profiles = _fixture_role_profiles()
	passing_posting = _fixture_posting()
	rejected_posting = passing_posting.model_copy(update={'url': 'https://boards.greenhouse.io/acme/jobs/2'})

	passing_result = RoleScreeningResult(
		role='Backend Engineer', used_fallback=False, screening=ScreeningResult(match_score=90, reasoning='n/a')
	)
	rejected_result = RoleScreeningResult(
		role='Backend Engineer', used_fallback=False, screening=ScreeningResult(match_score=40, reasoning='n/a')
	)

	applied_to = []

	async def fake_apply_to_posting(posting, role_profile, llm):
		applied_to.append(posting)
		return ApplicationOutcome(submitted=True, questions_encountered=[])

	monkeypatch.setattr(pipeline, 'apply_to_posting', fake_apply_to_posting)

	outcomes = await pipeline.apply_to_passing_postings(
		role_profiles,
		[(passing_posting, passing_result), (rejected_posting, rejected_result)],
		llm=SimpleNamespace(),
	)

	assert applied_to == [passing_posting]
	assert len(outcomes) == 1
	assert outcomes[0].submitted is True


async def test_run_chains_screening_into_applying(monkeypatch):
	role_profiles = _fixture_role_profiles()
	posting = _fixture_posting()
	screening_result = RoleScreeningResult(
		role='Backend Engineer', used_fallback=False, screening=ScreeningResult(match_score=90, reasoning='n/a')
	)

	async def fake_screen_new_postings(llm, role_resumes=None):
		return role_profiles, [(posting, screening_result)]

	async def fake_apply_to_passing_postings(profiles, screened, llm):
		assert profiles == role_profiles
		assert screened == [(posting, screening_result)]
		return [ApplicationOutcome(submitted=True, questions_encountered=[])]

	monkeypatch.setattr(pipeline, 'screen_new_postings', fake_screen_new_postings)
	monkeypatch.setattr(pipeline, 'apply_to_passing_postings', fake_apply_to_passing_postings)

	outcomes = await pipeline.run(llm=SimpleNamespace())

	assert len(outcomes) == 1
	assert outcomes[0].submitted is True
