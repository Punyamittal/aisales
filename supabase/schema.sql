-- AI Sales — Supabase schema (optional)
-- Run in Supabase SQL editor if you use Supabase.

-- Projects (from GitHub)
create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  repo_name text not null,
  description text,
  readme text,
  tech_stack text[],
  stars int default 0,
  forks int default 0,
  analysis jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Companies
create table if not exists companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  website text,
  product_info text,
  funding_info text,
  analysis jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Leads (contacts at companies)
create table if not exists leads (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references companies(id),
  email text,
  role text,
  name text,
  created_at timestamptz default now()
);

-- Outreach (sent emails)
create table if not exists outreach (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id),
  company_id uuid references companies(id),
  lead_id uuid references leads(id),
  email_body text,
  subject text,
  sent_at timestamptz,
  opened boolean default false,
  replied boolean default false,
  reply_text text,
  reply_analysis jsonb,
  outcome text,  -- no_reply, opened, reply, interested, meeting, deal
  reward real default 0,
  created_at timestamptz default now()
);

-- Rewards log (for learner)
create table if not exists reward_log (
  id uuid primary key default gen_random_uuid(),
  outreach_id uuid references outreach(id),
  category text,
  reward real,
  company_multiplier real default 1,
  created_at timestamptz default now()
);

-- Indexes
create index if not exists idx_outreach_sent on outreach(sent_at);
create index if not exists idx_outreach_outcome on outreach(outcome);
create index if not exists idx_projects_repo on projects(repo_name);
create index if not exists idx_companies_name on companies(name);
create index if not exists idx_leads_company on leads(company_id);
create index if not exists idx_outreach_project on outreach(project_id);
create index if not exists idx_outreach_company on outreach(company_id);
create index if not exists idx_reward_log_outreach on reward_log(outreach_id);

-- Trigger: keep updated_at in sync
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger projects_updated_at
  before update on projects
  for each row execute function set_updated_at();

create trigger companies_updated_at
  before update on companies
  for each row execute function set_updated_at();

-- Row Level Security (RLS) — enable and add policies as needed
alter table projects enable row level security;
alter table companies enable row level security;
alter table leads enable row level security;
alter table outreach enable row level security;
alter table reward_log enable row level security;

-- Example: allow service role / authenticated full access (tune for your auth)
create policy "Allow all for service role" on projects for all using (true) with check (true);
create policy "Allow all for service role" on companies for all using (true) with check (true);
create policy "Allow all for service role" on leads for all using (true) with check (true);
create policy "Allow all for service role" on outreach for all using (true) with check (true);
create policy "Allow all for service role" on reward_log for all using (true) with check (true);
