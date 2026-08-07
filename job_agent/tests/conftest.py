import pytest

from job_agent import config


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
	monkeypatch.setattr(config, 'DATA_DIR', tmp_path)
	monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'job_agent.sqlite3')
