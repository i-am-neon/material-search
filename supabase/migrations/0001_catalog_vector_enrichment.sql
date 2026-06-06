create extension if not exists "uuid-ossp";
create extension if not exists vector;

create table if not exists catalog_items (
  id uuid primary key default uuid_generate_v4(),
  manufacturer text not null,
  name text not null,
  material_family text,
  image_object_key text not null,
  image_url text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists catalog_items_material_family_idx
  on catalog_items (material_family);

create index if not exists catalog_items_metadata_gin_idx
  on catalog_items using gin (metadata);

create table if not exists catalog_embedding_models (
  id text primary key,
  dimensions int not null check (dimensions > 0),
  created_at timestamptz not null default now()
);

insert into catalog_embedding_models (id, dimensions)
values ('google/siglip2-so400m-patch14-384', 1152)
on conflict (id) do nothing;

create table if not exists catalog_item_embeddings (
  catalog_item_id uuid not null references catalog_items (id) on delete cascade,
  model_id text not null references catalog_embedding_models (id),
  dimensions int not null check (dimensions = 1152),
  embedding vector(1152) not null,
  created_at timestamptz not null default now(),
  primary key (catalog_item_id, model_id)
);

create index if not exists catalog_item_embeddings_model_idx
  on catalog_item_embeddings (model_id);

create index if not exists catalog_item_embeddings_vector_hnsw_idx
  on catalog_item_embeddings
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists catalog_items_set_updated_at on catalog_items;
create trigger catalog_items_set_updated_at
before update on catalog_items
for each row
execute function set_updated_at();

create or replace function match_catalog_items(
  query_embedding vector(1152),
  embedding_model_id text,
  match_count int default 12,
  min_similarity double precision default 0
)
returns table (
  catalog_item_id uuid,
  manufacturer text,
  name text,
  material_family text,
  image_object_key text,
  image_url text,
  metadata jsonb,
  created_at timestamptz,
  updated_at timestamptz,
  model_id text,
  similarity double precision
)
language sql
stable
as $$
  select
    ci.id as catalog_item_id,
    ci.manufacturer,
    ci.name,
    ci.material_family,
    ci.image_object_key,
    ci.image_url,
    ci.metadata,
    ci.created_at,
    ci.updated_at,
    cie.model_id,
    1 - (cie.embedding <=> query_embedding) as similarity
  from catalog_item_embeddings cie
  join catalog_items ci on ci.id = cie.catalog_item_id
  where cie.model_id = embedding_model_id
    and 1 - (cie.embedding <=> query_embedding) >= min_similarity
  order by cie.embedding <=> query_embedding
  limit match_count;
$$;

