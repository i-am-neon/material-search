create table if not exists material_search_runs (
  id uuid primary key default uuid_generate_v4(),
  prompt text not null,
  source_image_object_key text,
  source_image_url text,
  status text not null default 'running'
    check (status in ('running', 'completed', 'failed')),
  error text,
  image_width int check (image_width is null or image_width > 0),
  image_height int check (image_height is null or image_height > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (source_image_object_key is not null or source_image_url is not null)
);

create index if not exists material_search_runs_status_created_at_idx
  on material_search_runs (status, created_at desc);

create table if not exists material_search_regions (
  id uuid primary key default uuid_generate_v4(),
  run_id uuid not null references material_search_runs (id) on delete cascade,
  source_region_id text not null,
  prompt text not null,
  score double precision not null check (score >= 0 and score <= 1),
  box_xyxy jsonb not null,
  mask jsonb,
  crop_object_key text not null,
  crop_width int not null check (crop_width > 0),
  crop_height int not null check (crop_height > 0),
  embedding_model_id text not null references catalog_embedding_models (id),
  embedding_dimensions int not null check (embedding_dimensions > 0),
  status text not null default 'matched'
    check (status in ('matched', 'failed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (run_id, source_region_id)
);

create index if not exists material_search_regions_run_id_idx
  on material_search_regions (run_id);

create table if not exists material_search_matches (
  id uuid primary key default uuid_generate_v4(),
  run_id uuid not null references material_search_runs (id) on delete cascade,
  region_id uuid not null references material_search_regions (id) on delete cascade,
  catalog_item_id uuid not null references catalog_items (id) on delete cascade,
  embedding_model_id text not null references catalog_embedding_models (id),
  similarity double precision not null,
  rank int not null check (rank > 0),
  created_at timestamptz not null default now(),
  unique (region_id, rank),
  unique (region_id, catalog_item_id, embedding_model_id)
);

create index if not exists material_search_matches_run_id_idx
  on material_search_matches (run_id);

create index if not exists material_search_matches_region_id_rank_idx
  on material_search_matches (region_id, rank);

drop trigger if exists material_search_runs_set_updated_at on material_search_runs;
create trigger material_search_runs_set_updated_at
before update on material_search_runs
for each row
execute function set_updated_at();

drop trigger if exists material_search_regions_set_updated_at on material_search_regions;
create trigger material_search_regions_set_updated_at
before update on material_search_regions
for each row
execute function set_updated_at();
