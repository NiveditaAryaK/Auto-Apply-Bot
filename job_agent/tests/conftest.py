import pytest

from job_agent import config


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
	monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
	monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'job_agent.sqlite3')
	# RESUME_OUTPUT_DIR is derived from DATA_DIR at import time, not re-derived from it -- patch
	# separately so tests that render resumes don't write real PDFs into the repo's data dir.
	monkeypatch.setattr(config, 'RESUME_OUTPUT_DIR', tmp_path / 'resumes')
