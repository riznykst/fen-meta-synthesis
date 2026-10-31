-- FEN × Meta — Supabase access control and decision RPC (0002)
--
-- Security model (deliberate, mirrors SPEC §0.6 and T4):
--
--   anon / publishable key  → may SELECT registry_public only.
--                             No access to analyses, documents, items or
--                             decisions. No writes anywhere.
--   backend (service role)  → writes analyses/items; the only path to a
--                             decision is the record_decision() RPC below.
--
-- The publishable (anon) key is therefore safe to ship in the frontend: it
-- can read accepted knowledge and nothing else. The service-role key must
-- never reach the browser.

begin;

-- --------------------------------------------------------------- RLS ------
alter table public.analyses           enable row level security;
alter table public.analysis_documents enable row level security;
alter table public.items              enable row level security;
alter table public.decisions          enable row level security;

-- No policies are created for anon/authenticated on the base tables: with RLS
-- enabled and no policy, every access is denied. The service role bypasses RLS
-- by design (it is the governed write path).

-- Belt and braces: revoke table privileges from the API roles as well.
revoke all on public.analyses           from anon, authenticated;
revoke all on public.analysis_documents from anon, authenticated;
revoke all on public.items              from anon, authenticated;
revoke all on public.decisions          from anon, authenticated;

-- The public surface: a definer view (owner = postgres) that intentionally
-- bypasses RLS to expose exactly the accepted rows and nothing else.
grant usage on schema public to anon, authenticated;
grant select on public.registry_public to anon, authenticated;
grant select on public.item_status_current to service_role;

-- --------------------------------------------------------- record RPC ------
-- The single write path for human verdicts. Enforces in the database what the
-- UI and the demo API enforce in the application: an unverified quote can
-- never be accepted, and a decision always carries reviewer and reason.
create or replace function public.record_decision(
  p_analysis_id text,
  p_item_id     text,
  p_verdict     public.verdict,
  p_reviewer    text,
  p_comment     text default ''
)
returns public.decisions
language plpgsql
security definer
set search_path = public
as $$
declare
  v_analysis_id uuid;
  v_item        public.items;
  v_status      public.item_status;
  v_row         public.decisions;
begin
  if p_reviewer is null or length(btrim(p_reviewer)) = 0 then
    raise exception 'reviewer is required' using errcode = '22023';
  end if;

  select id into v_analysis_id
  from public.analyses
  where analysis_id = p_analysis_id;

  if v_analysis_id is null then
    raise exception 'unknown analysis_id: %', p_analysis_id using errcode = 'P0002';
  end if;

  select * into v_item
  from public.items
  where analysis_fk = v_analysis_id and item_id = p_item_id;

  if not found then
    raise exception 'unknown item_id % for analysis %', p_item_id, p_analysis_id
      using errcode = 'P0002';
  end if;

  -- The accept-lock: same rule as the UI button state and the HTTP 409.
  if p_verdict = 'accept' and not v_item.quote_verified then
    raise exception 'cannot accept an item with an unverified quote'
      using errcode = 'P0001';
  end if;

  v_status := case p_verdict
    when 'accept'  then 'accepted'::public.item_status
    when 'reject'  then 'rejected'::public.item_status
    else                'disputed'::public.item_status
  end;

  insert into public.decisions (
    decision_id, analysis_fk, item_fk, verdict, status, reviewer, comment
  )
  values (
    -- gen_random_uuid() is core Postgres (13+); pgcrypto lives in the
    -- `extensions` schema on Supabase, so it must not be relied on here.
    'dec_' || substr(replace(gen_random_uuid()::text, '-', ''), 1, 12),
    v_analysis_id, v_item.id, p_verdict, v_status,
    btrim(p_reviewer), coalesce(p_comment, '')
  )
  returning * into v_row;

  return v_row;
end $$;

comment on function public.record_decision(text, text, public.verdict, text, text) is
  'The only write path for human verdicts. Refuses accept on an unverified '
  'quote; inserts an immutable decision row.';

-- Only the governed backend may record decisions.
revoke all on function public.record_decision(text, text, public.verdict, text, text)
  from public, anon, authenticated;
grant execute on function public.record_decision(text, text, public.verdict, text, text)
  to service_role;

-- ------------------------------------------------------- realtime (opt) ----
-- Live registry updates in the UI. Non-fatal if the publication is absent.
do $$ begin
  alter publication supabase_realtime add table public.decisions;
exception when others then
  raise notice 'realtime publication not configured (skipped): %', sqlerrm;
end $$;

commit;
