# How to use AI Sales

## 1. One-time setup

### Install Ollama and a model
- Download and install [Ollama](https://ollama.com).
- Open a terminal and run:
  ```bash
  ollama pull llama3.2
  ```
- Leave Ollama running (it serves at `http://localhost:11434`).

### Backend env
- Go to the **backend** folder and create a `.env` file (copy from `backend/.env.example` or from the repo root `.env`).
- At minimum set:
  - `OLLAMA_BASE_URL=http://localhost:11434`
  - `OLLAMA_MODEL=llama3.2`
- Optional: `SUPABASE_*`, `GITHUB_TOKEN`, `RESEND_API_KEY` (see `docs/API_KEYS.md`).

### Install backend and frontend
- **Backend:** From repo root:
  ```bash
  cd backend
  python -m venv .venv
  .venv\Scripts\activate    # Windows
  pip install -r requirements.txt
  ```
- **Frontend:** From repo root:
  ```bash
  cd frontend
  npm install
  ```

---

## 2. Run the app (every time)

Use **two terminals**.

**Terminal 1 – Backend**
```bash
cd backend
.venv\Scripts\activate    # Windows; on Mac/Linux: source .venv/bin/activate
uvicorn main:app --reload
```
Wait until you see something like `Uvicorn running on http://127.0.0.1:8000`.

**Terminal 2 – Frontend**
```bash
cd frontend
npm run dev
```
Wait until you see `Ready on http://localhost:3000`.

---

## 3. Use the dashboard

Open **http://localhost:3000** in your browser.

### Step 1: Get project data (optional)
- In **“Fetch project from GitHub”**, type either:
  - `owner/repo` (e.g. `vercel/next.js`), or  
  - Full URL: `https://github.com/owner/repo`
- Click **Fetch** (or press Enter).
- The **Project (GitHub)** section below fills with repo name, description, README, tech stack, stars, and forks.  
  (If you don’t use Fetch, you can type or paste those fields yourself.)

### Step 2: Get suggested companies and contacts (optional)
- Click **Suggest companies**. The model analyzes your project and returns a list of **companies to contact** and the **representative roles to email** (e.g. CTO, VP Engineering) at each.
- Click **Use this company** on any row to fill the Company form and set the contact role.

### Step 3: Fill in the company
- In **Company**, enter (or use a suggested company): name, website, product info, funding/news, etc.

### Step 4: Run the pipeline
- Optionally set **Contact role** (e.g. “Decision Maker”, “CTO”).
- Check **Include pitch deck** if you want slide content.
- Click **Run pipeline**.

### Step 5: Use the results
- **Match** – Fit score and reasoning for this project–company pair.
- **Generated email body** – Copy and use (or edit) for outreach.
- **Pitch deck** – Slide titles and bullet points you can paste into slides.
- Expand **Full JSON** if you need the raw project/company analysis.

---

## 4. API-only usage

- **Docs:** http://localhost:8000/docs  
- **Health:** `GET http://localhost:8000/api/health`  
- **Full pipeline:** `POST http://localhost:8000/api/pipeline` with JSON body:
  ```json
  {
    "project": { "repo_name": "...", "description": "...", "readme": "...", "tech_stack": [], "stars": 0, "forks": 0 },
    "company": { "name": "...", "website": "...", "product_info": "...", "news": "", "funding_info": "", "job_postings": "" },
    "contact_role": "Decision Maker",
    "include_deck": true
  }
  ```
- **Fetch from GitHub:** `GET http://localhost:8000/api/github/repo?q=owner/repo`

---

## Troubleshooting

| Issue | What to do |
|-------|------------|
| Backend “Connection refused” to Ollama | Start Ollama (e.g. open the Ollama app or run `ollama serve`). |
| Frontend “Unreachable” / can’t run pipeline | Start the backend first; ensure it’s on port 8000 and frontend uses `NEXT_PUBLIC_API_URL=http://localhost:8000` if needed. |
| “Repo not found” on Fetch | Check `owner/repo` or URL; ensure `GITHUB_TOKEN` is in `backend/.env` for private repos or higher rate limits. |
| Pipeline slow or timeout | Ollama inference can take 30–120s per step; use a smaller/faster model (e.g. `llama3.2:1b`) or increase client timeout. |
