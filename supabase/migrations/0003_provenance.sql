-- 0003: provenance of the SOURCE document must survive into the durable store.
--
-- The API already classifies each document (primary / secondary / synthetic)
-- and echoes it on every claim. Without these columns that classification was
-- lost the moment a proposal was persisted, so the accepted knowledge in
-- `registry_public` could not say that its evidence came from a synthetic
-- commentary. Additive and idempotent.

alter table public.analysis_documents
  add column if not exists provenance text not null default 'primary';

alter table public.analysis_documents
  drop constraint if exists analysis_documents_provenance_check;
alter table public.analysis_documents
  add constraint analysis_documents_provenance_check
  check (provenance in ('primary', 'secondary', 'synthetic'));

alter table public.items
  add column if not exists provenance text not null default 'primary';

alter table public.items
  drop constraint if exists items_provenance_check;
alter table public.items
  add constraint items_provenance_check
  check (provenance in ('primary', 'secondary', 'synthetic'));

-- Expose it on the public surface: accepted knowledge must say when its
-- evidence came from a synthetic source. `primary` stays the quiet default.
-- NOTE: `provenance` is appended LAST on purpose — PostgreSQL matches
-- `create or replace view` columns by position, so inserting it mid-list
-- would fail with "cannot change name of view column".
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
  a.created_at as proposal_created_at,
  i.provenance
from public.item_status_current s
join public.items    i on i.id = s.item_fk
join public.analyses a on a.id = s.analysis_fk
where s.status = 'accepted'::public.item_status;

comment on view public.registry_public is
  'Read-only public surface: accepted items with provenance metadata (including the source document provenance) and no raw source text.';

grant select on public.registry_public to anon, authenticated;
