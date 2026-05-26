-- ──────────────────────────────────────────────────────────────
-- AI Sales CRM Copilot — Supabase Schema
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ──────────────────────────────────────────────────────────────

-- LEADS
create table if not exists leads (
  id            text primary key,
  name          text,
  company       text,
  email         text,
  phone         text,
  title         text,
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

-- DEALS
create table if not exists deals (
  id                   text primary key,
  lead_id              text references leads(id),
  title                text not null,
  stage                text default 'Discovery',
  value                numeric default 0,
  probability          integer default 0,
  expected_close_date  date,
  last_contact_date    date,
  rep_id               text,
  notes                text,
  created_at           timestamptz default now(),
  updated_at           timestamptz default now()
);

-- ACTIVITIES
create table if not exists activities (
  id          uuid primary key default gen_random_uuid(),
  deal_id     text references deals(id),
  type        text,  -- email | call | meeting | note | stage_change | deal_update
  summary     text,
  rep_id      text,
  created_at  timestamptz default now()
);

-- FOLLOW-UPS
create table if not exists follow_ups (
  id          uuid primary key default gen_random_uuid(),
  deal_id     text references deals(id),
  task        text,
  due_date    date,
  rep_id      text,
  priority    text default 'medium',
  status      text default 'pending',
  created_at  timestamptz default now()
);

-- EMAIL DRAFTS
create table if not exists email_drafts (
  id          uuid primary key default gen_random_uuid(),
  deal_id     text references deals(id),
  to_email    text,
  to_name     text,
  subject     text,
  body        text,
  rep_name    text,
  tone        text,
  status      text default 'pending_approval',
  created_at  timestamptz default now()
);

-- MCP CONTEXT
create table if not exists agent_context (
  session_id  text primary key,
  context     jsonb,
  updated_at  timestamptz default now()
);

-- INGESTION LOGS
create table if not exists ingestion_logs (
  id          uuid primary key default gen_random_uuid(),
  source      text,
  chunk_count integer default 0,
  status      text default 'success',
  created_at  timestamptz default now()
);

-- Enable Row Level Security (optional for production)
-- alter table leads enable row level security;
-- alter table deals enable row level security;

-- Indexes for performance
create index if not exists idx_deals_lead_id    on deals(lead_id);
create index if not exists idx_activities_deal  on activities(deal_id);
create index if not exists idx_followups_deal   on follow_ups(deal_id);
create index if not exists idx_drafts_deal      on email_drafts(deal_id);
create index if not exists idx_drafts_status    on email_drafts(status);
