from job_agent.resume.profile import EducationEntry, ExperienceBlock, ProjectBlock, ResumeProfile, SkillGroup
from job_agent.resume.render import render_resume
from job_agent.resume.selector import BlockSelection


def test_render_resume_produces_a_pdf(tmp_path):
	profile = ResumeProfile(
		full_name='Jane Doe',
		email='jane@example.com',
		phone='555-1234',
		location='Remote',
		summary='Backend engineer.',
		experience=[ExperienceBlock(id='exp-1', company='Acme', title='Engineer', start_date='2020', bullets=['Did things.'])],
		projects=[ProjectBlock(id='proj-1', name='Widget', description='A widget.', bullets=['Built it.'])],
		skills=[SkillGroup(id='skill-1', category='Languages', skills=['Python', 'Go'])],
		education=[EducationEntry(school='State U', degree='BS CS', end_date='2018')],
	)
	selection = BlockSelection(experience_ids=['exp-1'], project_ids=['proj-1'], skill_ids=['skill-1'])
	output_path = tmp_path / 'resume.pdf'

	result_path = render_resume(profile, selection, output_path)

	assert result_path == output_path
	assert output_path.exists()
	assert output_path.read_bytes().startswith(b'%PDF')


def test_render_resume_handles_empty_selections(tmp_path):
	profile = ResumeProfile(
		full_name='Jane Doe',
		email='jane@example.com',
		summary='Backend engineer.',
		experience=[],
		projects=[],
		skills=[],
		education=[],
	)
	selection = BlockSelection(experience_ids=[], project_ids=[], skill_ids=[])
	output_path = tmp_path / 'resume.pdf'

	render_resume(profile, selection, output_path)

	assert output_path.exists()
