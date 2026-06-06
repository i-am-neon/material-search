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

export type SegmentationRegionResponse = {
  id: string;
  prompt: string;
  score: number;
  box_xyxy: [number, number, number, number];
};

export type SegmentRegionMatchSetResponse = {
  region: SegmentationRegionResponse;
  crop_object_key: string;
  crop_url: string;
  crop_width: number;
  crop_height: number;
  model_id: string;
  dimensions: number;
  matches: RankedRegionMatchResponse[];
};

export type SegmentMatchResponse = {
  run_id: string;
  prompt: string;
  image_width: number;
  image_height: number;
  regions: SegmentRegionMatchSetResponse[];
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
