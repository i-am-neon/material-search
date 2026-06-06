import React from "react";
import {
  type SegmentMatchResponse,
  type SegmentRegionMatchSetResponse,
  createSearchRun,
  getSearchRunStatus,
  uploadSearchImage,
} from "../api";
import { defaultPrompt, matchesByRegion, regions as demoRegions } from "../demoData";
import { fileFromSample, type SampleImageOption } from "../samples";
import type { CatalogMetadata, MaterialRegion, ProductMatch, RunScenario } from "../types";

export type Surface = { region: MaterialRegion; matchCount: number; thumbUrl?: string };

export type UseSearchRunOptions = {
  initialScenario?: RunScenario;
  pollIntervalMs?: number;
  minAnalyzeMs?: number;
};

const DEFAULT_POLL_MS = 2000;
const DEFAULT_MIN_ANALYZE_MS = 800;
const POLL_ATTEMPTS = 90;

export function useSearchRun(options: UseSearchRunOptions = {}) {
  const {
    initialScenario = "empty",
    pollIntervalMs = DEFAULT_POLL_MS,
    minAnalyzeMs = DEFAULT_MIN_ANALYZE_MS,
  } = options;

  const [scenario, setScenario] = React.useState<RunScenario>(initialScenario);
  const [prompt, setPrompt] = React.useState(defaultPrompt);
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [selectedFileName, setSelectedFileName] = React.useState<string | undefined>();
  const [previewUrl, setPreviewUrl] = React.useState<string | undefined>();
  const [runResult, setRunResult] = React.useState<SegmentMatchResponse | null>(null);
  const [selectedRegionId, setSelectedRegionId] = React.useState(demoRegions[0].id);
  const [cartIds, setCartIds] = React.useState<string[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const previewObjectUrlRef = React.useRef<string | null>(null);
  const runSequenceRef = React.useRef(0);
  const selectionSeqRef = React.useRef(0);

  React.useEffect(() => {
    return () => {
      runSequenceRef.current = -1; // invalidate any in-flight run so it can't setState after unmount
      if (previewObjectUrlRef.current) URL.revokeObjectURL(previewObjectUrlRef.current);
    };
  }, []);

  const activeRegions: MaterialRegion[] = React.useMemo(
    () => (runResult ? mapRunRegions(runResult) : scenario === "complete" ? demoRegions : []),
    [runResult, scenario],
  );

  const matchesFor = React.useCallback(
    (regionId: string): ProductMatch[] => {
      if (runResult) return mapRunMatches(runResult, regionId);
      if (scenario === "complete") return matchesByRegion[regionId] ?? [];
      return [];
    },
    [runResult, scenario],
  );

  const surfaces: Surface[] = React.useMemo(
    () =>
      activeRegions.map((region) => {
        const matches = matchesFor(region.id);
        return { region, matchCount: matches.length, thumbUrl: matches[0]?.item.image_url ?? undefined };
      }),
    [activeRegions, matchesFor],
  );

  const selectedRegion =
    activeRegions.find((r) => r.id === selectedRegionId) ?? activeRegions[0];
  const selectedMatches = selectedRegion ? matchesFor(selectedRegion.id) : [];

  const cartItems = React.useMemo(
    () => activeRegions.flatMap((r) => matchesFor(r.id)).filter((m) => cartIds.includes(m.id)),
    [activeRegions, matchesFor, cartIds],
  );
  const cartSurfaceCount = React.useMemo(
    () => activeRegions.filter((r) => matchesFor(r.id).some((m) => cartIds.includes(m.id))).length,
    [activeRegions, matchesFor, cartIds],
  );

  const resetForNewImage = () => {
    setRunResult(null);
    setCartIds([]);
    setError(null);
    setScenario("empty");
    setSelectedRegionId(demoRegions[0].id);
  };

  const selectFile = (file: File) => {
    selectionSeqRef.current += 1;
    setSelectedFile(file);
    setSelectedFileName(file.name);
    resetForNewImage();
    if (previewObjectUrlRef.current) URL.revokeObjectURL(previewObjectUrlRef.current);
    previewObjectUrlRef.current = URL.createObjectURL(file);
    setPreviewUrl(previewObjectUrlRef.current);
  };

  const selectSample = async (sample: SampleImageOption) => {
    setError(null);
    const seq = (selectionSeqRef.current += 1);
    try {
      const file = await fileFromSample(sample);
      if (seq !== selectionSeqRef.current) return; // a newer selection superseded this one
      setSelectedFile(file);
      setSelectedFileName(sample.name);
      resetForNewImage();
      if (previewObjectUrlRef.current) {
        URL.revokeObjectURL(previewObjectUrlRef.current);
        previewObjectUrlRef.current = null;
      }
      setPreviewUrl(sample.src);
    } catch {
      if (seq !== selectionSeqRef.current) return;
      setError("Could not load the sample image. Try uploading your own image.");
    }
  };

  const run = async () => {
    if (!selectedFile) {
      setError("Choose a reference image before running search.");
      return;
    }
    setError(null);
    setRunResult(null);
    setCartIds([]);
    setScenario("planning");
    const seq = runSequenceRef.current + 1;
    runSequenceRef.current = seq;
    const startedAt = nowMs();
    try {
      const uploaded = await uploadSearchImage(selectedFile);
      const accepted = await createSearchRun({
        image_object_key: uploaded.image_object_key,
        prompt,
        confidence_threshold: 0.45,
        max_regions: 5,
        include_masks: false,
        matches_per_region: 6,
        min_similarity: 0,
      });
      if (seq !== runSequenceRef.current) return;
      setScenario("matching");
      const result = await pollSearchRun(accepted.run_id, pollIntervalMs);
      if (seq !== runSequenceRef.current) return;
      await ensureMinDuration(startedAt, minAnalyzeMs);
      if (seq !== runSequenceRef.current) return;
      setRunResult(result);
      setSelectedRegionId(result.regions[0]?.region.id ?? demoRegions[0].id);
      setScenario("complete");
    } catch (e) {
      if (seq !== runSequenceRef.current) return;
      setError(e instanceof Error ? e.message : "Search failed");
      setScenario("failed");
    }
  };

  const selectRegion = (id: string) => setSelectedRegionId(id);
  const toggleCart = (matchId: string) =>
    setCartIds((cur) => (cur.includes(matchId) ? cur.filter((x) => x !== matchId) : [...cur, matchId]));

  const isRunning = scenario === "planning" || scenario === "matching";

  return {
    scenario,
    prompt,
    setPrompt,
    selectedFileName,
    previewUrl,
    imageWidth: runResult?.image_width,
    imageHeight: runResult?.image_height,
    error,
    isRunning,
    selectFile,
    selectSample,
    run,
    surfaces,
    selectedRegionId: selectedRegion?.id ?? selectedRegionId,
    selectRegion,
    selectedRegion,
    selectedMatches,
    cartIds,
    toggleCart,
    cartItems,
    cartSurfaceCount,
  };
}

function nowMs(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}

async function ensureMinDuration(startedAt: number, minMs: number): Promise<void> {
  const elapsed = nowMs() - startedAt;
  if (elapsed < minMs) await delay(minMs - elapsed);
}

async function pollSearchRun(runId: string, intervalMs: number): Promise<SegmentMatchResponse> {
  for (let attempt = 0; attempt < POLL_ATTEMPTS; attempt += 1) {
    const status = await getSearchRunStatus(runId);
    if (status.run.status === "completed") {
      if (!status.result) throw new Error("Search completed without persisted results.");
      return status.result;
    }
    if (status.run.status === "failed") throw new Error(status.run.error ?? "Search failed");
    await delay(intervalMs);
  }
  throw new Error("Search is still running. Try refreshing the run status.");
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function mapRunRegions(result: SegmentMatchResponse): MaterialRegion[] {
  return result.regions.map((matchSet, index) => {
    const { region } = matchSet;
    const [x0, y0, x1, y1] = region.box_xyxy;
    return {
      id: region.id,
      label: matchSet.target_label ?? `Region ${index + 1}`,
      material: matchSet.target_label ?? region.prompt,
      confidence: confidenceLabel(region.score),
      box: {
        left: percent(x0, result.image_width),
        top: percent(y0, result.image_height),
        width: percent(x1 - x0, result.image_width),
        height: percent(y1 - y0, result.image_height),
      },
      note: `SAM3 identified this area with ${Math.round(region.score * 100)}% confidence.`,
      searchIntent: result.plan?.user_intent_summary ?? result.prompt,
      included: true,
      score: region.score,
    };
  });
}

function mapRunMatches(result: SegmentMatchResponse, regionId: string): ProductMatch[] {
  const matchSet = result.regions.find((c) => c.region.id === regionId);
  if (!matchSet) return [];
  return matchSet.matches.map((m) => ({
    id: `${regionId}-${m.match.item.id}`,
    fit: fitLabel(m.rank),
    item: {
      id: m.match.item.id,
      manufacturer: m.match.item.manufacturer,
      name: m.match.item.name,
      material_family: m.match.item.material_family,
      image_object_key: m.match.item.image_object_key,
      image_url: m.match.item.image_url,
      metadata: normalizeMetadata(m.match.item.metadata),
    },
    reasons: matchReasons(matchSet),
    similarity: m.match.similarity,
  }));
}

function matchReasons(matchSet: SegmentRegionMatchSetResponse): string[] {
  const lead = matchSet.region.prompt
    ? `Matches the ${matchSet.region.prompt} surface`
    : "Close visual + material match";
  return [lead, "Orderable catalog item"];
}

function normalizeMetadata(metadata: Record<string, unknown>): CatalogMetadata {
  return {
    colorway: stringValue(metadata.colorway),
    collection: stringValue(metadata.collection),
    image_kind: stringValue(metadata.image_kind),
    materials: stringArrayValue(metadata.materials),
    source_platform: stringValue(metadata.source_platform),
    source_url: stringValue(metadata.source_url),
    visual_tags: stringArrayValue(metadata.visual_tags),
  };
}

const stringValue = (v: unknown) => (typeof v === "string" ? v : undefined);
const stringArrayValue = (v: unknown) =>
  Array.isArray(v) && v.every((i) => typeof i === "string") ? (v as string[]) : undefined;

function percent(value: number, total: number): number {
  if (!total) return 0;
  return Math.max(0, Math.min(100, (value / total) * 100));
}

function confidenceLabel(score: number): MaterialRegion["confidence"] {
  if (score >= 0.8) return "High";
  if (score >= 0.55) return "Medium";
  return "Needs review";
}

function fitLabel(rank: number): ProductMatch["fit"] {
  if (rank === 1) return "Best fit";
  if (rank <= 3) return "Close alternate";
  return "Creative option";
}
