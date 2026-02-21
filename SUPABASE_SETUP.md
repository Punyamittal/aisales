# Supabase setup

## 1. Create `.env` (never commit this)

**Backend** — in `backend/`:

```env
SUPABASE_URL=https://warxrqrkjvadooyjbgdw.supabase.co
SUPABASE_ANON_KEY=<paste your anon key>
SUPABASE_SERVICE_KEY=<paste your service_role key>
```

**Frontend** — in `frontend/` (only if you call Supabase from the browser):

```env
NEXT_PUBLIC_SUPABASE_URL=https://warxrqrkjvadooyjbgdw.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<paste your anon key only>
```

- Use **anon key** in the frontend (and for public RLS).
- Use **service_role key** only in the backend; never expose it in the frontend.

## 2. Run the schema

1. Open [Supabase Dashboard](https://app.supabase.com) → your project.
2. Go to **SQL Editor**.
3. Paste the contents of `supabase/schema.sql`.
4. Run it.

## 3. Get your keys

**Project URL:** `https://warxrqrkjvadooyjbgdw.supabase.co`  
**Keys:** Project Settings → API → Project URL, `anon` (public), `service_role` (secret).

Keep `service_role` and any other secret keys only in `.env` and out of git.
