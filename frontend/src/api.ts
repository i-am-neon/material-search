const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export type UploadedImageResponse = {
  image_object_key: string;
  content_type: string;
  size_bytes: number;
};

export type SegmentMatchRequest = {
  image_object_key: string;
  prompt: string;
  confidence_threshold?: number;
  max_regions?: number;
  include_masks?: boolean;
  matches_per_region?: number;
  min_similarity?: number;
};

export type RawSam3SegmentRequest = {
  image_object_key?: string;
  image_url?: string;
  prompt: string;
  confidence_threshold?: number;
  max_regions?: number;
  include_masks?: boolean;
};

export type CatalogItemResponse = {
  id: string;
  manufacturer: string;
  name: string;
  material_family: string | null;
  image_object_key: string;
  image_url: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CatalogMatchResponse = {
  item: CatalogItemResponse;
  model_id: string;
  similarity: number;
};

export type RankedRegionMatchResponse = {
  region_id: string;
  rank: number;
  match: CatalogMatchResponse;
};

export type SegmentationMaskResponse = {
  format: "uncompressed_rle";
  size: [number, number];
  counts: number[];
};

export type SegmentationRegionResponse = {
  id: string;
  prompt: string;
  score: number;
  box_xyxy: [number, number, number, number];
  mask?: SegmentationMaskResponse | null;
};

export type RawSam3SegmentResponse = {
  model_id: string;
  image_width: number;
  image_height: number;
  prompt: string;
  regions: SegmentationRegionResponse[];
};

export type PlannedMaterialTargetResponse = {
  target_id: string;
  label: string;
  sam3_prompt: string;
  material_family_hint: string | null;
  reason: string;
  priority: number;
  max_regions: number;
};

export type MaterialSearchPlanResponse = {
  user_intent_summary: string;
  avoid: string[];
  targets: PlannedMaterialTargetResponse[];
};

export type SegmentRegionMatchSetResponse = {
  result_region_id: string;
  region: SegmentationRegionResponse;
  target_id: string | null;
  target_label: string | null;
  crop_object_key: string;
  crop_url: string | null;
  crop_width: number;
  crop_height: number;
  model_id: string;
  dimensions: number;
  matches: RankedRegionMatchResponse[];
};

export type SegmentMatchResponse = {
  run_id: string;
  prompt: string;
  plan: MaterialSearchPlanResponse | null;
  image_width: number;
  image_height: number;
  regions: SegmentRegionMatchSetResponse[];
};

export type SearchRunStatus = "queued" | "running" | "completed" | "failed";

export type SearchRunStage =
  | "queued"
  | "planning"
  | "segmenting"
  | "matching"
  | "complete"
  | "failed";

export type MaterialSearchRunResponse = {
  id: string;
  prompt: string;
  source_image_object_key: string | null;
  source_image_url: string | null;
  status: SearchRunStatus;
  stage?: SearchRunStage;
  intent_summary?: string | null;
  error: string | null;
  image_width: number | null;
  image_height: number | null;
  created_at: string;
  updated_at: string;
};

export type SearchRunAcceptedResponse = {
  run_id: string;
  status: SearchRunStatus;
};

export type ProgressSurfaceResponse = {
  result_region_id: string;
  label: string;
  box_xyxy: [number, number, number, number];
  score: number;
  status: "pending" | "matching" | "matched";
  match_count: number;
  thumb_url: string | null;
};

export type SearchRunProgressResponse = {
  stage: SearchRunStage;
  intent: string | null;
  planned_targets: string[];
  surfaces: ProgressSurfaceResponse[];
  image_width: number | null;
  image_height: number | null;
};

export type SearchRunStatusResponse = {
  run: MaterialSearchRunResponse;
  result: SegmentMatchResponse | null;
  progress?: SearchRunProgressResponse | null;
};

export async function uploadSearchImage(file: File): Promise<UploadedImageResponse> {
  const body = new FormData();
  body.append("image", file);

  const response = await fetch(apiUrl("/search/uploads"), {
    method: "POST",
    body,
  });
  return parseJsonResponse<UploadedImageResponse>(response);
}

export async function segmentMatches(
  request: SegmentMatchRequest,
): Promise<SegmentMatchResponse> {
  const response = await fetch(apiUrl("/search/segment-matches"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseJsonResponse<SegmentMatchResponse>(response);
}

export async function segmentSam3(
  request: RawSam3SegmentRequest,
): Promise<RawSam3SegmentResponse> {
  const response = await fetch(apiUrl("/dev/sam3/segment"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseJsonResponse<RawSam3SegmentResponse>(response);
}

export async function createSearchRun(
  request: SegmentMatchRequest,
): Promise<SearchRunAcceptedResponse> {
  const response = await fetch(apiUrl("/search/runs"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseJsonResponse<SearchRunAcceptedResponse>(response);
}

export async function getSearchRunStatus(runId: string): Promise<SearchRunStatusResponse> {
  const response = await fetch(apiUrl(`/search/runs/${runId}`));
  return parseJsonResponse<SearchRunStatusResponse>(response);
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : `Request failed with status ${response.status}`;
    throw new Error(detail);
  }
  return payload as T;
}

function apiUrl(path: string): string {
  return apiBaseUrl ? `${apiBaseUrl}${path}` : path;
}
