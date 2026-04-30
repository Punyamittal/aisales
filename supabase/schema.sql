create extension if not exists pgcrypto;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'pipeline_status') then
    create type pipeline_status as enum ('pending', 'running', 'success', 'failed');
  end if;
  if not exists (select 1 from pg_type where typname = 'email_status') then
    create type email_status as enum ('draft', 'sent', 'failed');
  end if;
end $$;

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  full_name text,
  phone text,
  location text,
  linkedin_url text,
  github_url text,
  avatar_url text,
  timezone text,
  is_active boolean not null default true,
  preferences jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  headline text,
  summary text,
  years_experience numeric(4,1),
  education jsonb not null default '[]'::jsonb,
  work_experience jsonb not null default '[]'::jsonb,
  projects jsonb not null default '[]'::jsonb,
  certifications jsonb not null default '[]'::jsonb,
  publications jsonb not null default '[]'::jsonb,
  parsed_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id)
);

create table if not exists target_preferences (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  target_role text not null,
  target_company text,
  experience_level text,
  location_preference text,
  employment_type text,
  work_mode text,
  salary_min numeric(12,2),
  salary_max numeric(12,2),
  priority jsonb not null default '{}'::jsonb,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists source_links (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  profile_id uuid references profiles(id) on delete cascade,
  link_type text not null,
  url text not null,
  title text,
  metadata jsonb not null default '{}'::jsonb,
  is_verified boolean not null default false,
  last_ingested_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, url)
);

create table if not exists companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  domain text,
  website_url text,
  linkedin_url text,
  industry text,
  size_range text,
  headquarters text,
  description text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (name),
  unique (domain)
);

create table if not exists job_listings (
  id uuid primary key default gen_random_uuid(),
  company_id uuid references companies(id) on delete set null,
  scraped_by_user_id uuid references users(id) on delete set null,
  source text not null,
  external_job_id text,
  title text not null,
  location text,
  employment_type text,
  work_mode text,
  seniority text,
  salary_text text,
  salary_min numeric(12,2),
  salary_max numeric(12,2),
  currency text,
  description text,
  apply_url text not null,
  raw_html text,
  posted_at timestamptz,
  expires_at timestamptz,
  is_active boolean not null default true,
  parsed_data jsonb not null default '{}'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source, external_job_id)
);

create table if not exists skills (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  category text,
  normalized_name text,
  aliases jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists profile_skills (
  profile_id uuid not null references profiles(id) on delete cascade,
  skill_id uuid not null references skills(id) on delete cascade,
  proficiency smallint,
  years_used numeric(4,1),
  source text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (profile_id, skill_id),
  check (proficiency is null or (proficiency >= 1 and proficiency <= 10))
);

create table if not exists job_skills (
  job_id uuid not null references job_listings(id) on delete cascade,
  skill_id uuid not null references skills(id) on delete cascade,
  is_required boolean not null default true,
  weight numeric(5,2),
  source text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (job_id, skill_id)
);

create table if not exists resume_versions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  profile_id uuid references profiles(id) on delete set null,
  target_preference_id uuid references target_preferences(id) on delete set null,
  job_id uuid references job_listings(id) on delete set null,
  version_no integer not null default 1,
  title text,
  latex_source text not null,
  pdf_url text,
  plain_text text,
  metadata jsonb not null default '{}'::jsonb,
  is_active boolean not null default true,
  generated_by text default 'ai',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, version_no)
);

create table if not exists ats_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  resume_version_id uuid not null references resume_versions(id) on delete cascade,
  job_id uuid references job_listings(id) on delete set null,
  score numeric(5,2) not null,
  keyword_match_pct numeric(5,2),
  formatting_score numeric(5,2),
  completeness_score numeric(5,2),
  readability_score numeric(5,2),
  missing_keywords jsonb not null default '[]'::jsonb,
  weak_bullets jsonb not null default '[]'::jsonb,
  formatting_issues jsonb not null default '[]'::jsonb,
  breakdown jsonb not null default '{}'::jsonb,
  suggestions jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (score >= 0 and score <= 100)
);

create table if not exists employees (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id) on delete cascade,
  discovered_by_user_id uuid references users(id) on delete set null,
  name text not null,
  role text,
  department text,
  linkedin_url text,
  email text,
  email_guess text,
  confidence numeric(5,2),
  source text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (company_id, linkedin_url),
  unique (company_id, email)
);

create table if not exists pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  profile_id uuid references profiles(id) on delete set null,
  target_preference_id uuid references target_preferences(id) on delete set null,
  job_id uuid references job_listings(id) on delete set null,
  resume_version_id uuid references resume_versions(id) on delete set null,
  status pipeline_status not null default 'pending',
  started_at timestamptz,
  completed_at timestamptz,
  duration_ms integer,
  error_message text,
  logs jsonb not null default '[]'::jsonb,
  metrics jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists cold_emails (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  pipeline_run_id uuid references pipeline_runs(id) on delete set null,
  employee_id uuid not null references employees(id) on delete cascade,
  company_id uuid references companies(id) on delete set null,
  job_id uuid references job_listings(id) on delete set null,
  resume_version_id uuid references resume_versions(id) on delete set null,
  email_type text not null,
  subject text not null,
  body text not null,
  personalization jsonb not null default '{}'::jsonb,
  status email_status not null default 'draft',
  sent_at timestamptz,
  provider_message_id text,
  failure_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists email_logs (
  id uuid primary key default gen_random_uuid(),
  cold_email_id uuid not null references cold_emails(id) on delete cascade,
  pipeline_run_id uuid references pipeline_runs(id) on delete set null,
  user_id uuid references users(id) on delete set null,
  provider text,
  status email_status not null,
  request_payload jsonb not null default '{}'::jsonb,
  response_payload jsonb not null default '{}'::jsonb,
  error_message text,
  event_time timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_profiles_user_id on profiles(user_id);
create index if not exists idx_target_preferences_user_id on target_preferences(user_id);
create index if not exists idx_source_links_user_id on source_links(user_id);
create index if not exists idx_source_links_profile_id on source_links(profile_id);

create index if not exists idx_job_listings_company_id on job_listings(company_id);
create index if not exists idx_job_listings_scraped_by_user_id on job_listings(scraped_by_user_id);
create index if not exists idx_job_listings_source on job_listings(source);
create index if not exists idx_job_listings_posted_at on job_listings(posted_at desc);
create index if not exists idx_job_listings_is_active on job_listings(is_active);

create index if not exists idx_profile_skills_profile_id on profile_skills(profile_id);
create index if not exists idx_profile_skills_skill_id on profile_skills(skill_id);

create index if not exists idx_job_skills_job_id on job_skills(job_id);
create index if not exists idx_job_skills_skill_id on job_skills(skill_id);

create index if not exists idx_resume_versions_user_id on resume_versions(user_id);
create index if not exists idx_resume_versions_job_id on resume_versions(job_id);
create index if not exists idx_resume_versions_profile_id on resume_versions(profile_id);

create index if not exists idx_ats_reports_user_id on ats_reports(user_id);
create index if not exists idx_ats_reports_job_id on ats_reports(job_id);
create index if not exists idx_ats_reports_resume_version_id on ats_reports(resume_version_id);

create index if not exists idx_employees_company_id on employees(company_id);
create index if not exists idx_employees_discovered_by_user_id on employees(discovered_by_user_id);
create index if not exists idx_employees_role on employees(role);

create index if not exists idx_pipeline_runs_user_id on pipeline_runs(user_id);
create index if not exists idx_pipeline_runs_job_id on pipeline_runs(job_id);
create index if not exists idx_pipeline_runs_status on pipeline_runs(status);
create index if not exists idx_pipeline_runs_created_at on pipeline_runs(created_at desc);

create index if not exists idx_cold_emails_user_id on cold_emails(user_id);
create index if not exists idx_cold_emails_company_id on cold_emails(company_id);
create index if not exists idx_cold_emails_job_id on cold_emails(job_id);
create index if not exists idx_cold_emails_pipeline_run_id on cold_emails(pipeline_run_id);
create index if not exists idx_cold_emails_employee_id on cold_emails(employee_id);
create index if not exists idx_cold_emails_status on cold_emails(status);

create index if not exists idx_email_logs_cold_email_id on email_logs(cold_email_id);
create index if not exists idx_email_logs_pipeline_run_id on email_logs(pipeline_run_id);
create index if not exists idx_email_logs_user_id on email_logs(user_id);
create index if not exists idx_email_logs_status on email_logs(status);
create index if not exists idx_email_logs_event_time on email_logs(event_time desc);

drop trigger if exists trg_users_set_updated_at on users;
create trigger trg_users_set_updated_at before update on users
for each row execute function set_updated_at();

drop trigger if exists trg_profiles_set_updated_at on profiles;
create trigger trg_profiles_set_updated_at before update on profiles
for each row execute function set_updated_at();

drop trigger if exists trg_target_preferences_set_updated_at on target_preferences;
create trigger trg_target_preferences_set_updated_at before update on target_preferences
for each row execute function set_updated_at();

drop trigger if exists trg_source_links_set_updated_at on source_links;
create trigger trg_source_links_set_updated_at before update on source_links
for each row execute function set_updated_at();

drop trigger if exists trg_companies_set_updated_at on companies;
create trigger trg_companies_set_updated_at before update on companies
for each row execute function set_updated_at();

drop trigger if exists trg_job_listings_set_updated_at on job_listings;
create trigger trg_job_listings_set_updated_at before update on job_listings
for each row execute function set_updated_at();

drop trigger if exists trg_skills_set_updated_at on skills;
create trigger trg_skills_set_updated_at before update on skills
for each row execute function set_updated_at();

drop trigger if exists trg_profile_skills_set_updated_at on profile_skills;
create trigger trg_profile_skills_set_updated_at before update on profile_skills
for each row execute function set_updated_at();

drop trigger if exists trg_job_skills_set_updated_at on job_skills;
create trigger trg_job_skills_set_updated_at before update on job_skills
for each row execute function set_updated_at();

drop trigger if exists trg_resume_versions_set_updated_at on resume_versions;
create trigger trg_resume_versions_set_updated_at before update on resume_versions
for each row execute function set_updated_at();

drop trigger if exists trg_ats_reports_set_updated_at on ats_reports;
create trigger trg_ats_reports_set_updated_at before update on ats_reports
for each row execute function set_updated_at();

drop trigger if exists trg_employees_set_updated_at on employees;
create trigger trg_employees_set_updated_at before update on employees
for each row execute function set_updated_at();

drop trigger if exists trg_pipeline_runs_set_updated_at on pipeline_runs;
create trigger trg_pipeline_runs_set_updated_at before update on pipeline_runs
for each row execute function set_updated_at();

drop trigger if exists trg_cold_emails_set_updated_at on cold_emails;
create trigger trg_cold_emails_set_updated_at before update on cold_emails
for each row execute function set_updated_at();

drop trigger if exists trg_email_logs_set_updated_at on email_logs;
create trigger trg_email_logs_set_updated_at before update on email_logs
for each row execute function set_updated_at();
