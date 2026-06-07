export type RunScenario = "empty" | "planning" | "matching" | "complete" | "failed";

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

/**
 * Live progress of a search run, streamed to the client while the LangGraph
 * pipeline executes (plan -> segment -> match). A ProgressSnapshot is one
 * partial view of the run; the client receives a sequence of them.
 */
export type ProgressStage = "planning" | "segmenting" | "matching" | "complete";

/** Per-surface state during the run. A surface is segmented first, then matched. */
export type ProgressSurfaceStatus = "pending" | "matching" | "matched";

export type ProgressSurface = {
  id: string;
  label: string;
  box: RegionBox;
  score?: number;
  status: ProgressSurfaceStatus;
  /** Number of catalog matches found (once matched). */
  matchCount?: number;
  /** Thumbnail of the top match (once matched). */
  thumbUrl?: string;
};

export type ProgressSnapshot = {
  stage: ProgressStage;
  /** Plain-language intent, available once planning completes. */
  intent?: string;
  /** Target labels chosen by the planner, before boxes are resolved. */
  plannedTargets?: string[];
  /** Resolved surfaces with boxes, populated from segmenting onward. */
  surfaces: ProgressSurface[];
  previewUrl?: string;
  imageWidth?: number;
  imageHeight?: number;
};

export type MatchFit = "Best fit" | "Close alternate" | "Creative option";

export type ProductMatch = {
  id: string;
  fit: MatchFit;
  item: CatalogSeedItem;
  reasons: string[];
  similarity?: number; // 0..1 visual similarity when produced by a real run
};
