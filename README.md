# job_agent

Personal job-application automation. Given one or more resumes, it finds new matching postings
on Greenhouse/Lever boards, screens each one against whichever resume fits it best, and submits
an application through a real browser for anything that passes screening.

Built on top of the [`browser_use`](browser_use/) library, which lives in this repo and drives
the actual browser (CDP, DOM extraction, LLM-driven actions).

## Pipeline

```
Resume(s) --> role inference --+
                                v
config.TARGET_COMPANIES --> Web Search Agent --> HR Agent --> Browser-Use apply --> db.applications
                          (discovery/search_agent.py)  (hr_agent.py)   (apply_agent.py)
```

1. **Resume / role inference** (`resume/roles.py`) -- every resume listed in `config.ROLE_RESUMES`
   is parsed (`resume/parse.py`) into a `ResumeProfile`, and an LLM derives a short role label
   (e.g. "Backend Engineer") straight from that resume's own content. No fixed role list --
   exactly one resume must be flagged `is_primary=True` as the fallback.
2. **Web Search Agent** (`discovery/search_agent.py`) -- polls every board in
   `config.TARGET_COMPANIES` via the Greenhouse/Lever adapters (`discovery/greenhouse.py`,
   `discovery/lever.py`), keeps postings matching `config.KEYWORDS`, and drops anything already
   seen in a previous run (`db.seen_jobs`).
3. **HR Agent** (`hr_agent.py`) -- for each new posting, picks whichever resume/role best fits it
   (falling back to the primary resume if none are a clear fit) and scores the match 0-100 the
   way an ATS + first-pass recruiter would. Every screening is recorded to `db.applications` as
   `screened_pass` or `screened_reject` against `config.MATCH_SCORE_THRESHOLD`.
4. **Browser-Use apply step** (`apply_agent.py`) -- for postings that passed, tailors a resume
   PDF (`resume/selector.py` + `resume/render.py`) and drives a real `browser_use.Agent` through
   the actual application form (file upload, field fill, submit). Throttled per-domain via
   `config.RATE_LIMITS`. Outcome recorded as `applied`, `apply_failed`, or `rate_limited`.

`pipeline.py` wires all of this together:

- `pipeline.screen_new_postings(llm)` -- steps 1-3, returns `(role_profiles, [(posting, result), ...])`.
- `pipeline.apply_to_passing_postings(role_profiles, screened, llm)` -- step 4 for the postings
  that passed screening.
- `pipeline.run(llm)` -- the whole thing end to end.

## Setup

1. `uv venv --python 3.11 && source .venv/bin/activate && uv sync`
2. Copy `.env.example` to `.env` and set `JOB_AGENT_LLM_BASE_URL` / `JOB_AGENT_LLM_API_KEY` /
   `JOB_AGENT_LLM_MODEL` -- defaults to a local LM Studio server; swap for any OpenAI-compatible
   endpoint. `job_agent/config.py` reads these directly (no hardcoded fallback in source).
3. Populate `job_agent/config.py`:
   - `ROLE_RESUMES` -- path to each resume PDF/DOCX, exactly one with `is_primary=True`. Optional
     if you're managing resumes through the web UI instead (see below) -- that stores them in the
     `resumes` db table and builds this same list dynamically.
   - `TARGET_COMPANIES` -- Greenhouse board tokens / Lever company slugs to watch.
   - `KEYWORDS` -- case-insensitive substrings a posting's title/JD must contain.
   - `RATE_LIMITS` -- per-domain apply caps (defaults are conservative for LinkedIn/Indeed).
4. `uv run python -c "import asyncio; from job_agent.pipeline import run; asyncio.run(run())"`

Data lives in `job_agent/data/` (sqlite tracker + rendered per-application resumes), created on
first use.

## Web UI

A FastAPI backend (`job_agent/api/`) and a React/Vite frontend (`frontend/`) for uploading
resumes and tracking applications without touching `config.py` or the sqlite db directly.

```
uv run uvicorn job_agent.api.service:app --reload   # backend on :8000
cd frontend && npm install && npm run dev            # frontend on :5173 (proxies /api to :8000)
```

Open `http://localhost:5173`. The **Resumes** tab uploads/manages resumes (stored under
`job_agent/data/uploads/`, tracked in the `resumes` db table -- the first upload is always
primary, and `resume/roles.py`'s "exactly one primary" invariant is enforced on every write) --
dropping a resume there also starts a pipeline run automatically (skipped if one's already in
flight, since the running one already has the resume list it started with). The **Run Pipeline**
button in the header does the same on demand. While a run is active its live status (discovery /
screening / applying, with counts) is polled onto the button; the **Dashboard** tab shows every
screened/applied posting as it's recorded. If the backend process dies or reloads mid-run, the
run is left `failed` (rather than stuck `running` forever) the next time the API starts up.

## Tests

```
uv run pytest -vxs job_agent/tests
uv run pytest -vxs tests/ci   # browser_use library's own test suite
```

## Credits

The browser driving this (`browser_use/`, vendored in this repo) is [Browser Use](https://github.com/browser-use/browser-use)
by Gregor Žunič and Magnus Müller, licensed under the [MIT License](LICENSE). `job_agent/` is a
personal application built on top of it.

`job_agent/tests` never hits real job boards or a real browser -- discovery/LLM/browser-use calls
are all injected via fakes at the function boundary (`adapters=`, `llm=`, `_run_apply_agent`).
`job_agent/tests/api` covers the FastAPI routes and run orchestration the same way (`runner.pipeline.run`
monkeypatched).
