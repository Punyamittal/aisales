# AI Sales

Autonomous AI Business and Career Agent: convert GitHub projects into job opportunities, clients, and revenue.

**Flow:** Code → Analysis → Companies → Leads → Pitch → Email + Deck → Replies → Learning → Optimization

## Stack

- **Backend:** FastAPI, Ollama (local LLM), optional Supabase & Resend
- **Frontend:** Next.js 14, TypeScript, Tailwind
- **Prompts:** Multi-agent prompts in `prompts/` + master `system_prompt.txt` for Ollama

## Quick start

### 1. Ollama

Install [Ollama](https://ollama.com) and pull a model:

```bash
ollama pull llama3.2
```

Keep Ollama running (default: `http://localhost:11434`).

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
cp ../.env.example .env
# Edit .env: OLLAMA_MODEL, optional SUPABASE_*, RESEND_API_KEY
# From backend/ directory:
uvicorn main:app --reload
```

Ensure you run from inside `backend/` so `config` and `app` resolve. From repo root:

```bash
cd backend && uvicorn main:app --reload
```

API: http://localhost:8000 — Docs: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Set `NEXT_PUBLIC_API_URL=http://localhost:8000` if your API is elsewhere.

### 4. Optional: Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. In SQL Editor, run `supabase/schema.sql`.
3. In backend `.env`, set `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.

### 5. Optional: Email (Resend)

Set `RESEND_API_KEY` and `EMAIL_FROM` in backend `.env` to send real emails via `app.services.email_service`.

## Project layout

```
aisales/
├── system_prompt.txt       # Master Ollama system prompt
├── cursor-master-prompt.md # Cursor system prompt (copy to Settings → AI)
├── .cursor/rules/          # Cursor project rule (active)
├── prompts/                # Agent prompts (analyzer, researcher, matcher, …)
├── backend/
│   ├── main.py             # FastAPI app
│   ├── config.py           # Settings from env
│   ├── app/
│   │   ├── agents/         # Ollama client + runner (per-agent)
│   │   ├── models/         # Pydantic schemas
│   │   ├── services/       # Orchestrator, rewards, email
│   │   ├── api/            # Routes
│   │   └── db/             # Supabase client
│   └── requirements.txt
├── frontend/               # Next.js dashboard
│   ├── app/
│   ├── components/
│   └── package.json
└── supabase/
    └── schema.sql          # Optional DB schema
```

## API overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/suggest-companies` | POST | Suggest companies to contact + representative roles to email (from project) |
| `/api/pipeline` | POST | Full pipeline: project + company → analysis, match, email, deck |
| `/api/analyze/project` | POST | Analyze GitHub project |
| `/api/analyze/company` | POST | Analyze company |
| `/api/match` | POST | Match project to company (analysis dicts) |
| `/api/pitch/email` | POST | Generate outreach email |
| `/api/pitch/deck` | POST | Generate pitch deck content |
| `/api/sender/plan` | POST | Sending strategy (time, volume, risk) |
| `/api/reply/analyze` | POST | Analyze email reply (intent, next action) |
| `/api/learner` | POST | RL-style strategy update |
| `/api/manager` | POST | Orchestrator next tasks |
| `/api/rewards` | GET | Reward model (category → value) |

## Reward model

- No reply: 0  
- Opened: 1  
- Reply: 3  
- Interested: 7  
- Meeting: 10  
- Deal: 20  

Multiply by company strategic value for weighted rewards.

## License

MIT.
# aisales
