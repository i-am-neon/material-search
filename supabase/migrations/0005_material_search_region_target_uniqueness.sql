alter table material_search_regions
  drop constraint if exists material_search_regions_run_id_source_region_id_key;

create unique index if not exists material_search_regions_run_target_source_region_uidx
  on material_search_regions (run_id, target_id, source_region_id);
