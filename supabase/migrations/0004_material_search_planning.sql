create table if not exists material_search_targets (
  id uuid primary key default uuid_generate_v4(),
  run_id uuid not null references material_search_runs (id) on delete cascade,
  target_id text not null,
  label text not null,
  sam3_prompt text not null,
  material_family_hint text,
  reason text not null,
  priority int not null check (priority > 0),
  max_regions int not null check (max_regions > 0),
  avoid jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (run_id, target_id)
);

create index if not exists material_search_targets_run_id_priority_idx
  on material_search_targets (run_id, priority);

alter table material_search_regions
  add column if not exists target_id text,
  add column if not exists target_label text;

drop trigger if exists material_search_targets_set_updated_at on material_search_targets;
create trigger material_search_targets_set_updated_at
before update on material_search_targets
for each row
execute function set_updated_at();
