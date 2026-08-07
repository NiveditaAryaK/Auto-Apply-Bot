from types import SimpleNamespace

from job_agent.resume.profile import ExperienceBlock, ProjectBlock, ResumeProfile, SkillGroup
from job_agent.resume.selector import BlockSelection, select_blocks


def _fixture_profile() -> ResumeProfile:
	return ResumeProfile(
		full_name='Jane Doe',
		email='jane@example.com',
		summary='Backend engineer.',
		experience=[
			ExperienceBlock(id='exp-1', company='Acme', title='Engineer', start_date='2020', bullets=['Did things.']),
			ExperienceBlock(id='exp-2', company='Beta', title='SWE', start_date='2018', end_date='2020', bullets=['Did other things.']),
		],
		projects=[
			ProjectBlock(id='proj-1', name='Widget', description='A widget.', bullets=['Built it.']),
			ProjectBlock(id='proj-2', name='Gadget', description='A gadget.', bullets=['Built that too.']),
		],
		skills=[SkillGroup(id='skill-1', category='Languages', skills=['Python', 'Go'])],
		education=[],
	)


class _FakeLLM:
	def __init__(self, completion: BlockSelection):
		self._completion = completion

	async def ainvoke(self, *_args, **_kwargs):
		return SimpleNamespace(completion=self._completion)


async def test_select_blocks_respects_valid_llm_selection():
	profile = _fixture_profile()
	fake_llm = _FakeLLM(BlockSelection(experience_ids=['exp-2', 'exp-1'], project_ids=['proj-1'], skill_ids=['skill-1']))

	selection = await select_blocks(profile, jd_text='some JD', llm=fake_llm)

	assert selection.experience_ids == ['exp-2', 'exp-1']
	assert selection.project_ids == ['proj-1']
	assert selection.skill_ids == ['skill-1']


async def test_select_blocks_drops_hallucinated_ids():
	profile = _fixture_profile()
	fake_llm = _FakeLLM(
		BlockSelection(experience_ids=['exp-1', 'exp-made-up'], project_ids=['proj-made-up'], skill_ids=['skill-made-up'])
	)

	selection = await select_blocks(profile, jd_text='some JD', llm=fake_llm)

	# exp-1 kept (valid + LLM-ordered), exp-2 appended since it was dropped from the LLM's list.
	assert selection.experience_ids == ['exp-1', 'exp-2']
	assert selection.project_ids == []
	assert selection.skill_ids == []


async def test_select_blocks_never_drops_experience_even_if_llm_omits_it():
	profile = _fixture_profile()
	fake_llm = _FakeLLM(BlockSelection(experience_ids=[], project_ids=[], skill_ids=[]))

	selection = await select_blocks(profile, jd_text='some JD', llm=fake_llm)

	assert set(selection.experience_ids) == {'exp-1', 'exp-2'}
