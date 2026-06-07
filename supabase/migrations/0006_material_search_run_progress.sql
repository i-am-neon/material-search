-- Live progress for search runs: a finer-grained stage within the run lifecycle,
-- the persisted planner intent, and the resolved segments (boxes) so the client
-- can render surfaces as soon as SAM3 returns, before matching completes.

alter table material_search_runs
  add column if not exists stage text not null default 'queued'
    check (stage in ('queued', 'planning', 'segmenting', 'matching', 'complete', 'failed'));

alter table material_search_runs
  add column if not exists intent_summary text;

alter table material_search_runs
  add column if not exists segments jsonb;
