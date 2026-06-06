import React from "react";
import { Download, Grid2X2, Layers3, ShoppingCart } from "lucide-react";
import { Link } from "react-router-dom";
import {
  type SegmentMatchResponse,
  type SegmentRegionMatchSetResponse,
  createSearchRun,
  getSearchRunStatus,
  uploadSearchImage,
} from "../api";
import { defaultPrompt, getRunStages, matchesByRegion, regions } from "../demoData";
import type { CatalogMetadata, MaterialRegion, ProductMatch, RunScenario } from "../types";
import { RegionCanvas } from "./RegionCanvas";
import { RegionInspector } from "./RegionInspector";
import { RunTimeline } from "./RunTimeline";
import { SearchSetup, type SampleImageOption } from "./SearchSetup";

type SearchWorkbenchProps = {
  initialScenario?: RunScenario;
};

export function SearchWorkbench({ initialScenario = "complete" }: SearchWorkbenchProps) {
  const [scenario, setScenario] = React.useState<RunScenario>(initialScenario);
  const [selectedRegionId, setSelectedRegionId] = React.useState(regions[0].id);
  const [cartIds, setCartIds] = React.useState<string[]>([]);
  const [prompt, setPrompt] = React.useState(defaultPrompt);
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [selectedFileName, setSelectedFileName] = React.useState<string | undefined>();
  const [previewUrl, setPreviewUrl] = React.useState<string | undefined>();
  const [runResult, setRunResult] = React.useState<SegmentMatchResponse | null>(null);
  const [activeRunId, setActiveRunId] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const previewObjectUrlRef = React.useRef<string | null>(null);
  const runSequenceRef = React.useRef(0);
  const dynamicRegions = runResult ? mapRunRegions(runResult) : null;
  const activeRegions = dynamicRegions?.length ? dynamicRegions : regions;
  const selectedRegion =
    activeRegions.find((region) => region.id === selectedRegionId) ?? activeRegions[0];
  const selectedMatches =
    runResult && selectedRegion
      ? mapRunMatches(runResult, selectedRegion.id)
      : scenario === "complete"
        ? matchesByRegion[selectedRegion.id]
        : [];
  const stageLabel =
    (runResult?.run_id ?? activeRunId)?.slice(0, 8).toUpperCase() ??
    (scenario === "empty" ? "NEW RUN" : scenario === "failed" ? "RUN-2406-F" : "RUN-2406");
  const isRunning = scenario === "planning" || scenario === "matching";

  React.useEffect(() => {
    return () => {
      if (previewObjectUrlRef.current) {
        URL.revokeObjectURL(previewObjectUrlRef.current);
      }
    };
  }, []);

  const handleToggleCart = (matchId: string) => {
    setCartIds((current) =>
      current.includes(matchId) ? current.filter((id) => id !== matchId) : [...current, matchId],
    );
  };

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setSelectedFileName(file.name);
    setRunResult(null);
    setActiveRunId(null);
    setCartIds([]);
    setError(null);
    setScenario("empty");
    setSelectedRegionId(regions[0].id);
    if (previewObjectUrlRef.current) {
      URL.revokeObjectURL(previewObjectUrlRef.current);
    }
    previewObjectUrlRef.current = URL.createObjectURL(file);
    setPreviewUrl(previewObjectUrlRef.current);
  };

  const handleSampleSelect = async (sample: SampleImageOption) => {
    setError(null);
    try {
      const file = await fileFromSample(sample);
      setSelectedFile(file);
      setSelectedFileName(sample.name);
      setRunResult(null);
      setActiveRunId(null);
      setCartIds([]);
      setScenario("empty");
      setSelectedRegionId(regions[0].id);
      if (previewObjectUrlRef.current) {
        URL.revokeObjectURL(previewObjectUrlRef.current);
        previewObjectUrlRef.current = null;
      }
      setPreviewUrl(sample.src);
    } catch {
      setError("Could not load the sample image. Try uploading your own image.");
    }
  };

  const handleRun = async () => {
    if (!selectedFile) {
      setError("Choose a reference image before running search.");
      return;
    }

    setError(null);
    setRunResult(null);
    setActiveRunId(null);
    setCartIds([]);
    setScenario("planning");
    const runSequence = runSequenceRef.current + 1;
    runSequenceRef.current = runSequence;
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
      if (runSequence !== runSequenceRef.current) {
        return;
      }
      setActiveRunId(accepted.run_id);
      setScenario("matching");
      const result = await pollSearchRun(accepted.run_id);
      if (runSequence !== runSequenceRef.current) {
        return;
      }
      setRunResult(result);
      setSelectedRegionId(result.regions[0]?.region.id ?? regions[0].id);
      setScenario("complete");
    } catch (runError) {
      if (runSequence !== runSequenceRef.current) {
        return;
      }
      setError(runError instanceof Error ? runError.message : "Search failed");
      setScenario("failed");
    }
  };

  return (
    <main className={`app-shell ${scenario === "empty" ? "intake-shell" : ""}`}>
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true">
          <Layers3 size={22} />
        </div>
        <div>
          <p className="eyebrow">Material Search</p>
          <h1>Find orderable materials from a reference image</h1>
        </div>
        <div className="topbar-actions">
          <Link className="nav-action" to="/catalog">
            <Grid2X2 size={18} />
            <span>Catalog</span>
          </Link>
          <button className="icon-button cart-icon" aria-label="Sample cart" type="button">
            <ShoppingCart size={18} />
            <span>{cartIds.length}</span>
          </button>
          <button className="icon-button" aria-label="Export run" type="button">
            <Download size={18} />
          </button>
        </div>
      </header>

      {scenario === "empty" ? (
        <SearchSetup
          scenario={scenario}
          prompt={prompt}
          selectedFileName={selectedFileName}
          previewUrl={previewUrl}
          isRunning={isRunning}
          error={error}
          layout="page"
          onPromptChange={setPrompt}
          onFileSelect={handleFileSelect}
          onSampleSelect={handleSampleSelect}
          onRun={handleRun}
        />
      ) : (
        <section className="workspace-grid">
          <SearchSetup
            scenario={scenario}
            prompt={prompt}
            selectedFileName={selectedFileName}
            previewUrl={previewUrl}
            isRunning={isRunning}
            error={error}
            onPromptChange={setPrompt}
            onFileSelect={handleFileSelect}
            onSampleSelect={handleSampleSelect}
            onRun={handleRun}
          />

          <div className="center-stack">
            <RunTimeline stages={getRunStages(scenario)} runLabel={stageLabel} />
            <RegionCanvas
              regions={activeRegions}
              selectedRegionId={selectedRegionId}
              scenario={scenario}
              imageSrc={previewUrl}
              imageTitle={selectedFileName ? "Uploaded reference" : undefined}
              imageAlt={selectedFileName ?? undefined}
              imageWidth={runResult?.image_width}
              imageHeight={runResult?.image_height}
              onSelectRegion={setSelectedRegionId}
            />
          </div>

          <RegionInspector
            region={selectedRegion}
            matches={selectedMatches}
            cartIds={cartIds}
            onToggleCart={handleToggleCart}
          />
        </section>
      )}
    </main>
  );
}

const SEARCH_POLL_INTERVAL_MS = 2000;
const SEARCH_POLL_ATTEMPTS = 90;

async function pollSearchRun(runId: string): Promise<SegmentMatchResponse> {
  for (let attempt = 0; attempt < SEARCH_POLL_ATTEMPTS; attempt += 1) {
    const status = await getSearchRunStatus(runId);
    if (status.run.status === "completed") {
      if (!status.result) {
        throw new Error("Search completed without persisted results.");
      }
      return status.result;
    }
    if (status.run.status === "failed") {
      throw new Error(status.run.error ?? "Search failed");
    }
    await delay(SEARCH_POLL_INTERVAL_MS);
  }
  throw new Error("Search is still running. Try refreshing the run status.");
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function fileFromSample(sample: SampleImageOption): Promise<File> {
  const response = await fetch(sample.src);
  if (!response.ok) {
    throw new Error(`Could not load sample image ${sample.id}`);
  }
  const blob = await response.blob();
  return new File([blob], sample.filename, { type: blob.type || "image/png" });
}

function mapRunRegions(result: SegmentMatchResponse): MaterialRegion[] {
  return result.regions.map(({ region }, index) => {
    const [x0, y0, x1, y1] = region.box_xyxy;
    const confidence = confidenceLabel(region.score);
    return {
      id: region.id,
      label: `Region ${index + 1}`,
      material: region.prompt,
      confidence,
      box: {
        left: percent(x0, result.image_width),
        top: percent(y0, result.image_height),
        width: percent(x1 - x0, result.image_width),
        height: percent(y1 - y0, result.image_height),
      },
      note: `SAM3 identified this area with ${Math.round(region.score * 100)}% confidence.`,
      searchIntent: result.prompt,
      included: true,
      score: region.score,
    };
  });
}

function mapRunMatches(result: SegmentMatchResponse, regionId: string): ProductMatch[] {
  const matchSet = result.regions.find((candidate) => candidate.region.id === regionId);
  if (!matchSet) {
    return [];
  }
  return matchSet.matches.map((match) => ({
    id: `${regionId}-${match.match.item.id}`,
    fit: fitLabel(match.rank),
    item: {
      id: match.match.item.id,
      manufacturer: match.match.item.manufacturer,
      name: match.match.item.name,
      material_family: match.match.item.material_family,
      image_object_key: match.match.item.image_object_key,
      image_url: match.match.item.image_url,
      metadata: normalizeMetadata(match.match.item.metadata),
    },
    reasons: matchReasons(matchSet, match.match.similarity),
  }));
}

function matchReasons(matchSet: SegmentRegionMatchSetResponse, similarity: number): string[] {
  const reasons = [`${Math.round(similarity * 100)}% visual similarity`];
  if (matchSet.region.prompt) {
    reasons.push(matchSet.region.prompt);
  }
  reasons.push("orderable catalog item");
  return reasons;
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

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function stringArrayValue(value: unknown): string[] | undefined {
  return Array.isArray(value) && value.every((item) => typeof item === "string") ? value : undefined;
}

function percent(value: number, total: number): number {
  if (!total) {
    return 0;
  }
  return Math.max(0, Math.min(100, (value / total) * 100));
}

function confidenceLabel(score: number): MaterialRegion["confidence"] {
  if (score >= 0.8) {
    return "High";
  }
  if (score >= 0.55) {
    return "Medium";
  }
  return "Needs review";
}

function fitLabel(rank: number): ProductMatch["fit"] {
  if (rank === 1) {
    return "Best fit";
  }
  if (rank <= 3) {
    return "Close alternate";
  }
  return "Creative option";
}
