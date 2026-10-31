-- FEN × Meta — Supabase schema (0001)
--
-- Domain model of the hackathon workflow, moved from the demo's in-memory /
-- JSONL registry into Postgres:
--
--   analyses 1─┬─* analysis_documents   (source documents, server-only)
--              └─* items                (claims and contradictions)
--                    └─* decisions      (append-only human verdicts)
--
-- Rules encoded in the schema itself (not only in the app):
--   * an analysis starts as 'proposed' — there is no way to create it decided;
--   * a claim must carry a quote and a document_id;
--   * a contradiction must reference at least two claims;
--   * a decision's status always matches its verdict;
--   * decisions are immutable (trigger below) and append-only;
--   * `accept` on an unverified quote is refused by the RPC (0002).
--
-- Apply with `psql "$SUPABASE_DB_URL" -f 0001_schema.sql` or through the
-- Supabase SQL editor. Safe to re-run (idempotent guards throughout).

begin;

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- enums ----
do $$ begin
  create type public.item_type as enum ('claim', 'contradiction');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.item_status as enum ('proposed', 'accepted', 'rejected', 'disputed');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.verdict as enum ('accept', 'reject', 'dispute');
exception when duplicate_object then null; end $$;

-- ------------------------------------------------------------ analyses ----
create table if not exists public.analyses (
  id                 uuid primary key default gen_random_uuid(),
  analysis_id        text not null unique,
  -- A fresh analysis is always 'proposed'; the column exists so that a future
  -- analysis-level lifecycle does not need a migration, but nothing may set
  -- it to a decided value at insert time.
  status             public.item_status not null default 'proposed'
                     check (status = 'proposed'),
  model_provider     text,
  model_requested    text,
  model_returned     text,
  prompt_hash        text not null,
  created_at         timestamptz not null default now(),
  latency_ms         integer check (latency_ms is null or latency_ms >= 0),
  usage              jsonb,
  provenance_check   jsonb not null default '{}'::jsonb
);

comment on table public.analyses is
  'One model run over a set of source documents. Server-side only.';

-- ------------------------------------------------- source documents --------
create table if not exists public.analysis_documents (
  analysis_fk  uuid not null references public.analyses(id) on delete cascade,
  document_id  text not null,
  title        text,
  content      text not null,
  char_count   integer generated always as (length(content)) stored,
  primary key (analysis_fk, document_id)
);

comment on table public.analysis_documents is
  'Verbatim source text supplied for one analysis. Never exposed to anon: '
  'quotes are checked against this content server-side.';

-- ---------------------------------------------------------------- items ----
create table if not exists public.items (
  id                          uuid primary key default gen_random_uuid(),
  analysis_fk                 uuid not null references public.analyses(id) on delete cascade,
  item_id                     text not null,
  item_type                   public.item_type not null,

  -- claim fields
  statement                   text,
  quote                       text,
  interpretation              text,
  document_id                 text,
  uncertainty                 text,
  review_recommendation       text,
  ambiguities                 text[] not null default '{}',

  -- provenance result computed by code, never by the model
  quote_verified              boolean not null,
  provenance_status           text,

  -- contradiction fields
  contradiction_kind          text,
  explanation                 text,
  alternative_interpretations text[] not null default '{}',
  claim_ids                   text[] not null default '{}',

  unique (analysis_fk, item_id),

  constraint claim_needs_evidence check (
    item_type <> 'claim'
    or (quote is not null and length(btrim(quote)) > 0 and document_id is not null)
  ),
  constraint contradiction_needs_two_claims check (
    item_type <> 'contradiction'
    or coalesce(array_length(claim_ids, 1), 0) >= 2
  ),
  constraint contradiction_needs_explanation check (
    item_type <> 'contradiction'
    or (explanation is not null and length(btrim(explanation)) > 0)
  )
);

comment on column public.items.quote_verified is
  'Computed by deterministic code against analysis_documents.content. '
  'The only field that gates acceptance.';

create index if not exists items_analysis_idx on public.items (analysis_fk);
create index if not exists items_item_id_idx  on public.items (item_id);
create index if not exists items_verified_idx on public.items (quote_verified);

-- ------------------------------------------------------------ decisions ----
create table if not exists public.decisions (
  id              uuid primary key default gen_random_uuid(),
  decision_id     text not null unique,
  analysis_fk     uuid not null references public.analyses(id) on delete cascade,
  item_fk         uuid not null references public.items(id) on delete cascade,
  verdict         public.verdict not null,
  status          public.item_status not null,
  reviewer        text not null check (length(btrim(reviewer)) > 0),
  comment         text not null default '',
  recorded_at     timestamptz not null default now(),
  event_published boolean not null default false,

  constraint verdict_status_matches check (
    (verdict = 'accept'  and status = 'accepted')
    or (verdict = 'reject'  and status = 'rejected')
    or (verdict = 'dispute' and status = 'disputed')
  )
);

comment on table public.decisions is
  'Append-only human verdicts. Re-deciding inserts a new row; nothing is updated.';

create index if not exists decisions_item_idx
  on public.decisions (item_fk, recorded_at desc);
create index if not exists decisions_analysis_idx
  on public.decisions (analysis_fk);
create index if not exists decisions_recorded_idx
  on public.decisions (recorded_at desc);
create index if not exists decisions_reviewer_idx
  on public.decisions (reviewer);

-- Immutability: a recorded verdict is evidence of a human act; editing or
-- deleting it would destroy the audit trail (SPEC T4).
create or replace function public.decisions_are_immutable()
returns trigger
language plpgsql
as $$
begin
  raise exception 'decisions are immutable: % is not allowed (record a new decision instead)',
    tg_op
    using errcode = 'P0001';
end $$;

drop trigger if exists decisions_no_update on public.decisions;
create trigger decisions_no_update
  before update or delete on public.decisions
  for each row execute function public.decisions_are_immutable();

-- ------------------------------------------------------------- views ------
-- Latest decision per item: the item's current status.
create or replace view public.item_status_current as
select
  i.id            as item_fk,
  i.analysis_fk,
  i.item_id,
  i.item_type,
  coalesce(d.status, 'proposed'::public.item_status) as status,
  d.decision_id,
  d.reviewer,
  d.verdict,
  d.comment,
  d.recorded_at
from public.items i
left join lateral (
  select dd.*
  from public.decisions dd
  where dd.item_fk = i.id
  order by dd.recorded_at desc, dd.id desc
  limit 1
) d on true;

-- Public registry: accepted knowledge only, without raw source text.
-- This is the one surface the frontend may read with the publishable key.
create or replace view public.registry_public as
select
  s.analysis_fk,
  s.item_id,
  s.item_type,
  s.status,
  i.statement,
  i.quote,
  i.document_id,
  i.interpretation,
  i.uncertainty,
  i.quote_verified,
  i.contradiction_kind,
  i.alternative_interpretations,
  s.reviewer,
  s.verdict,
  s.comment,
  s.recorded_at,
  s.decision_id,
  a.analysis_id,
  a.model_returned,
  a.prompt_hash,
  a.created_at as proposal_created_at
from public.item_status_current s
join public.items    i on i.id = s.item_fk
join public.analyses a on a.id = s.analysis_fk
where s.status = 'accepted'::public.item_status;

comment on view public.registry_public is
  'Read-only public surface: accepted items with provenance metadata and no '
  'source-document text. Exposes only what a human accepted.';

commit;
