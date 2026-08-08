from dataclasses import dataclass
from pathlib import Path

JOB_AGENT_DIR = Path(__file__).resolve().parent
DATA_DIR = JOB_AGENT_DIR / 'data'
DB_PATH = DATA_DIR / 'job_agent.sqlite3'
RESUME_SOURCE_PATH = DATA_DIR / 'resume_source.pdf'
RESUME_OUTPUT_DIR = DATA_DIR / 'resumes'

# LM Studio local server (OpenAI-compatible endpoint), model id must match what LM Studio reports
# at GET /v1/models exactly (e.g. 'openai/gpt-oss-20b', not 'gpt-oss-20b').
LLM_BASE_URL = 'http://localhost:1234/v1'
LLM_API_KEY = 'lm-studio'
LLM_MODEL = 'openai/gpt-oss-20b'

MATCH_SCORE_THRESHOLD = 80


@dataclass
class TargetCompany:
	"""A company board to watch. Greenhouse/Lever have no cross-company keyword-search API,
	so discovery is per-company: you tell the adapter which company boards to poll, and results
	are filtered client-side by KEYWORDS."""

	name: str
	ats_platform: str  # 'greenhouse' | 'lever'
	board_token: str  # greenhouse board token, or lever company slug


# Populate with real board tokens before running, e.g.:
# TargetCompany(name='Example Co', ats_platform='greenhouse', board_token='examplecoinc'),
TARGET_COMPANIES: list[TargetCompany] = []

# Case-insensitive substrings matched against title + jd_text.
KEYWORDS: list[str] = []

# Per-domain rate limits for the apply step (not discovery). 'default' applies to any domain
# not listed explicitly. Adversarial ATS/job-board domains (LinkedIn, Indeed) get a tight cap.
RATE_LIMITS: dict[str, dict[str, int]] = {
	'default': {'max_per_hour': 20, 'jitter_seconds': 60},
	'linkedin.com': {'max_per_hour': 4, 'jitter_seconds': 300},
	'indeed.com': {'max_per_hour': 4, 'jitter_seconds': 300},
}
