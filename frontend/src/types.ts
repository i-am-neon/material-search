export type RunScenario = "empty" | "planning" | "matching" | "complete" | "failed";

export type RunStageStatus = "complete" | "active" | "queued" | "failed";

export type RunStage = {
  label: string;
  detail: string;
  status: RunStageStatus;
};

export type RegionBox = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export type MaterialRegion = {
  id: string;
  label: string;
  material: string;
  confidence: "High" | "Medium" | "Needs review";
  box: RegionBox;
  note: string;
  searchIntent: string;
  included: boolean;
  score?: number;
};

export type CatalogMetadata = {
  colorway?: string;
  collection?: string;
  image_kind?: string;
  materials?: string[];
  source_platform?: string;
  source_url?: string;
  visual_tags?: string[];
};

export type CatalogSeedItem = {
  id?: string;
  manufacturer: string;
  name: string;
  material_family: string | null;
  image_object_key: string;
  image_url: string | null;
  metadata: CatalogMetadata;
};

export type MatchFit = "Best fit" | "Close alternate" | "Creative option";

export type ProductMatch = {
  id: string;
  fit: MatchFit;
  item: CatalogSeedItem;
  reasons: string[];
};
