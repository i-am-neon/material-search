alter table material_search_runs
  drop constraint if exists material_search_runs_status_check;

alter table material_search_runs
  add constraint material_search_runs_status_check
  check (status in ('queued', 'running', 'completed', 'failed'));

alter table material_search_runs
  alter column status set default 'queued';
