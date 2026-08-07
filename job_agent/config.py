from dataclasses import dataclass
from pathlib import Path

JOB_AGENT_DIR = Path(__file__).resolve().parent
DATA_DIR = JOB_AGENT_DIR / 'data'
DB_PATH = DATA_DIR / 'job_agent.sqlite3'
RESUME_OUTPUT_DIR = DATA_DIR / 'resumes'

# LM Studio local server (OpenAI-compatible endpoint), model id must match what LM Studio reports
# at GET /v1/models exactly (e.g. 'openai/gpt-oss-20b', not 'gpt-oss-20b').
LLM_BASE_URL = 'http://localhost:1234/v1'
LLM_API_KEY = 'lm-studio'
LLM_MODEL = 'openai/gpt-oss-20b'

MATCH_SCORE_THRESHOLD = 80


@dataclass
class RoleResume:
	"""One of the candidate's resumes. Which role/specialization it targets is inferred from the
	resume's own content (see resume/roles.py) rather than configured here -- only the file and
	primary flag are user-provided. Discovery still runs a single broad search across all roles
	(see KEYWORDS below); hr_agent.route_and_screen uses the inferred roles to pick which resume
	best fits each posting found, falling back to the primary resume when none are a clear fit."""

	resume_path: Path
	is_primary: bool = False


# Exactly one entry must have is_primary=True -- resume/roles.py validates this at load time.
# Example:
#   RoleResume(resume_path=DATA_DIR / 'resume_backend.pdf', is_primary=True),
#   RoleResume(resume_path=DATA_DIR / 'resume_applied_ai.pdf'),
ROLE_RESUMES: list[RoleResume] = []


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
