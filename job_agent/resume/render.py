from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from job_agent.resume.profile import ResumeProfile
from job_agent.resume.selector import BlockSelection


def render_resume(profile: ResumeProfile, selection: BlockSelection, output_path: Path) -> Path:
	output_path.parent.mkdir(parents=True, exist_ok=True)
	styles = getSampleStyleSheet()
	heading_style = ParagraphStyle('BlockHeading', parent=styles['Heading2'], spaceBefore=10, spaceAfter=4)
	body_style = styles['BodyText']

	experience_by_id = {e.id: e for e in profile.experience}
	project_by_id = {p.id: p for p in profile.projects}
	skill_by_id = {s.id: s for s in profile.skills}

	story = [
		Paragraph(profile.full_name, styles['Title']),
		Paragraph(' | '.join(filter(None, [profile.email, profile.phone, profile.location])), body_style),
		Spacer(1, 0.15 * inch),
		Paragraph(profile.summary, body_style),
	]

	if selection.experience_ids:
		story.append(Paragraph('Experience', heading_style))
		for block_id in selection.experience_ids:
			block = experience_by_id[block_id]
			date_range = f'{block.start_date} - {block.end_date or "Present"}'
			story.append(Paragraph(f'<b>{block.title}</b>, {block.company} ({date_range})', body_style))
			story.append(ListFlowable([ListItem(Paragraph(b, body_style)) for b in block.bullets], bulletType='bullet'))

	if selection.project_ids:
		story.append(Paragraph('Projects', heading_style))
		for block_id in selection.project_ids:
			block = project_by_id[block_id]
			story.append(Paragraph(f'<b>{block.name}</b> - {block.description}', body_style))
			story.append(ListFlowable([ListItem(Paragraph(b, body_style)) for b in block.bullets], bulletType='bullet'))

	if selection.skill_ids:
		story.append(Paragraph('Skills', heading_style))
		for block_id in selection.skill_ids:
			block = skill_by_id[block_id]
			story.append(Paragraph(f'<b>{block.category}:</b> {", ".join(block.skills)}', body_style))

	if profile.education:
		story.append(Paragraph('Education', heading_style))
		for edu in profile.education:
			story.append(Paragraph(f'{edu.degree}, {edu.school} ({edu.end_date or ""})', body_style))

	SimpleDocTemplate(str(output_path), pagesize=LETTER, topMargin=0.6 * inch, bottomMargin=0.6 * inch).build(story)
	return output_path
