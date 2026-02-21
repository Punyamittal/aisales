# API keys & environment variables

## Required to run the app

| Variable | Where to get it | Used by |
|----------|-----------------|--------|
| **Ollama** | No key. Install [Ollama](https://ollama.com), run it locally. | Backend (LLM) |
| `OLLAMA_BASE_URL` | Default `http://localhost:11434` | Backend |
| `OLLAMA_MODEL` | e.g. `llama3.2` after `ollama pull llama3.2` | Backend |

You can run the full pipeline (analyze → match → pitch → deck) with **only Ollama**; Supabase and Resend are optional.

---

## Optional but recommended

| Variable | Where to get it | Used by |
|----------|-----------------|--------|
| **Supabase** | [supabase.com](https://supabase.com) → your project → **Settings → API** | Backend (and frontend if you add Supabase client) |
| `SUPABASE_URL` | Project URL, e.g. `https://xxxxx.supabase.co` | Backend |
| `SUPABASE_ANON_KEY` | Anon (public) key | Backend / Frontend |
| `SUPABASE_SERVICE_KEY` | Service role key (secret) | Backend only |

Without Supabase: app still works; you just don’t persist projects, companies, outreach, or rewards in the DB.

---

## Optional: sending real emails

| Variable | Where to get it | Used by |
|----------|-----------------|--------|
| **Resend** | [resend.com](https://resend.com) → API Keys | Backend |
| `RESEND_API_KEY` | Create API key in Resend dashboard | Backend |
| `EMAIL_FROM` | Verified domain or Resend sandbox, e.g. `onboarding@resend.dev` | Backend |
| `EMAIL_FROM_NAME` | Display name, e.g. `AI Sales` | Backend |

Without Resend: pipeline still generates email **content**; it just won’t send it. Backend logs “RESEND_API_KEY not set; skipping send”.

---

## Optional: app security

| Variable | Where to get it | Used by |
|----------|-----------------|--------|
| `API_SECRET_KEY` | Any long random string for signing/verifying server requests | Backend |
| `ENVIRONMENT` | `development` or `production` | Backend |

Use a strong random value in production (e.g. `openssl rand -hex 32`).

---

## Optional: fetch repo from GitHub

| Variable | Where to get it | Used by |
|----------|-----------------|--------|
| `GITHUB_TOKEN` | [GitHub → Personal access tokens](https://github.com/settings/tokens) | Backend `/api/github/repo` |

Used by **Fetch from GitHub** in the dashboard: fills project from repo (description, README, languages, stars, forks). Without it, GitHub rate limits are stricter; with it you can also access private repos (token needs `repo` scope).

---

## Optional: contact enrichment (emails when suggesting companies)

| Variable | Where to get it | Used by |
|----------|-----------------|--------|
| `HUNTER_API_KEY` | [Hunter.io → API](https://hunter.io/api) | Backend when suggesting companies |

When you click **Suggest companies**, the model returns companies and optional **company_domain** (e.g. `stripe.com`). The backend finds contacts in two ways: (1) **Hunter.io** — if `HUNTER_API_KEY` is set, it calls Domain Search for each domain (name, email, title). (2) **Beautiful Soup scraper** — if Hunter returns no contacts (or no key), it scrapes the company website (home, /contact, /about, /team) and extracts emails from the HTML. So you can get emails even without Hunter; the scraper runs automatically as a fallback.

---

## Future / not implemented yet

| Service | Variable | Purpose |
|---------|----------|--------|
| **Other LLM** | e.g. `OPENAI_API_KEY` | If you add a cloud LLM as fallback alongside Ollama. |

---

## Summary

- **Minimum to run:** Ollama (no key).
- **To persist data:** Supabase (URL + anon + service_role).
- **To send emails:** Resend (API key + from address).
- **GitHub fetch:** `GITHUB_TOKEN` in `backend/.env` for “Fetch from GitHub”.
- **Contact enrichment:** **Apollo** (optional) for people in senior roles + LinkedIn links; **Hunter** (optional) for emails; **Beautiful Soup** scraper fallback. Set `APOLLO_API_KEY` to surface decision-makers by title; set `HUNTER_API_KEY` for best email coverage.
- **For production:** Set `API_SECRET_KEY` and `ENVIRONMENT=production`.

Put all secrets in `.env` (or `backend/.env`) and never commit that file.
