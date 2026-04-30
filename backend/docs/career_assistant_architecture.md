# AI Career Assistant Architecture

## Backend Modules

- `profile-service`: `app/services/career_services.py::ProfileService`
- `job-service`: `app/services/career_services.py::JobService`
- `resume-service`: `app/services/career_services.py::ResumeService`
- `ats-service`: `app/services/career_services.py::AtsService` + `app/services/ats_engine.py`
- `employee-service`: `app/services/career_services.py::EmployeeService`
- `email-service`: `app/services/career_services.py::EmailService` + `app/services/email_service.py`
- `pipeline-orchestrator`: `app/services/pipeline_orchestrator_service.py`
- `scraper-engine`: `app/services/scraper_engine.py` + `app/services/scraper_contacts.py`

## API Routes

- `POST /api/profile/ingest`
- `GET /api/jobs/search`
- `POST /api/resume/generate`
- `POST /api/ats/analyze`
- `GET /api/employees/find`
- `POST /api/emails/generate`
- `POST /api/pipeline/run`
- `GET /api/pipeline/{run_id}`
- `GET /api/pipeline/{run_id}/steps`

## Pipeline Flow

1. Input role/company/links
2. Scrape profile sources (GitHub/LinkedIn public pages)
3. Scrape careers pages and rank jobs
4. Generate tailored LaTeX resume and compile PDF locally
5. Run rule-based ATS scoring
6. Discover employees (scraped, with heuristic email fallback)
7. Generate template-based personalized outreach emails
8. Persist step outputs in in-memory stores + pipeline run tracking

## No External API Constraint

- No OpenAI/external AI API usage in career assistant flow.
- Optional local AI supported through local Ollama only.
# AI Career Assistant Backend Architecture

## Textual Architecture Diagram

```text
[Client/UI]
   |
   v
[FastAPI API Layer]
   |
   +--> /profile/*  -> ProfileService
   +--> /jobs/*     -> JobService
   +--> /resume/*   -> ResumeService
   +--> /ats/*      -> AtsService
   +--> /employees/*-> EmployeeService
   +--> /emails/*   -> EmailService
   +--> /pipeline/* -> PipelineOrchestratorService
                      |
                      +--> async queue worker
                      +--> step tracking + run state
   |
   +--> Supabase (planned persistence target)
```

## Pipeline Flow

`input -> jobs -> resume -> ats -> outreach`

1. `POST /api/pipeline/run` queues run with profile and constraints.
2. Worker selects qualified jobs from `JobService`.
3. Worker generates targeted resume via `ResumeService`.
4. Worker analyzes ATS score via `AtsService`.
5. If threshold passes, worker finds contacts and drafts outreach using `EmployeeService` + `EmailService`.
6. Results and step statuses are available with `GET /api/pipeline/{run_id}` and `GET /api/pipeline/{run_id}/steps`.

## API Contract Table

| Module | Endpoint | Method | Description |
|---|---|---|---|
| profile-service | `/api/profile/ingest` | POST | Ingest and normalize candidate profile |
| job-service | `/api/jobs/search` | GET | Search ranked jobs by profile/query |
| resume-service | `/api/resume/generate` | POST | Generate targeted resume |
| ats-service | `/api/ats/analyze` | POST | Evaluate ATS compatibility |
| employee-service | `/api/employees/find` | GET | Find recruiters/managers for outreach |
| email-service | `/api/emails/generate` | POST | Generate personalized outreach email |
| pipeline-orchestrator | `/api/pipeline/run` | POST | Queue async end-to-end pipeline run |
| pipeline-orchestrator | `/api/pipeline/{run_id}` | GET | Retrieve current run status/results |
| pipeline-orchestrator | `/api/pipeline/{run_id}/steps` | GET | Retrieve run step timeline |

## Error Handling Strategy

- Standard error envelope:
  - `error.code`, `error.message`, `error.details`, `error.retryable`
  - `request_id` included in every error response
- Request middleware attaches `x-request-id`, logs latency, and echoes header in response.
- Global exception handlers return consistent JSON for `HTTPException` and unhandled failures.

## Logging Strategy

- Structured application logs include:
  - request id, method, path, status, latency
  - orchestrator lifecycle events and step outcomes
- Errors are logged with stack traces using centralized exception handler.

## Async Job Handling

- `PipelineOrchestratorService` maintains:
  - in-memory queue (`asyncio.Queue`)
  - background worker task
  - run record store with step-level metadata
- Run statuses: `queued`, `running`, `completed`, `failed`, `partial`.
- Designed to be replaced by Redis/Celery/BullMQ style queue without changing API contracts.
