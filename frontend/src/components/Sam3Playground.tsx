import React from "react";
import { ArrowLeft, Braces, ImagePlus, Loader2, Play, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import {
  type RawSam3SegmentResponse,
  type SegmentationRegionResponse,
  segmentSam3,
  uploadSearchImage,
} from "../api";
import { measureImageDimensions, type ImageDimensions } from "../lib/imageDimensions";
import type { MaterialRegion } from "../types";
import { ReferenceStage } from "./studio/ReferenceStage";
import { Button } from "./ui/button";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "same-origin";

type Sam3PlaygroundProps = {
  initialPrompt?: string;
  initialPreviewUrl?: string;
  initialResult?: RawSam3SegmentResponse;
};

export function Sam3Playground({
  initialPrompt = "green upholstery",
  initialPreviewUrl,
  initialResult,
}: Sam3PlaygroundProps) {
  const fileInputId = React.useId();
  const [prompt, setPrompt] = React.useState(initialPrompt);
  const [imageUrl, setImageUrl] = React.useState(initialPreviewUrl ?? "");
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [selectedFileName, setSelectedFileName] = React.useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = React.useState(initialPreviewUrl);
  const [previewImageDimensions, setPreviewImageDimensions] = React.useState<ImageDimensions | null>(
    initialResult ? { width: initialResult.image_width, height: initialResult.image_height } : null,
  );
  const [confidenceThreshold, setConfidenceThreshold] = React.useState(0.5);
  const [maxRegions, setMaxRegions] = React.useState(20);
  const [includeMasks, setIncludeMasks] = React.useState(true);
  const [result, setResult] = React.useState<RawSam3SegmentResponse | null>(initialResult ?? null);
  const [selectedRegionId, setSelectedRegionId] = React.useState(
    initialResult?.regions[0]?.id ?? "",
  );
  const [error, setError] = React.useState<string | null>(null);
  const [isRunning, setIsRunning] = React.useState(false);
  const objectUrlRef = React.useRef<string | null>(null);
  const imageSelectionSeqRef = React.useRef(0);

  React.useEffect(() => {
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, []);

  const regions = React.useMemo(() => (result ? mapSam3Regions(result) : []), [result]);
  const selectedRegion = regions.find((region) => region.id === selectedRegionId) ?? regions[0];
  const displayPreviewUrl = previewUrl || imageUrl || undefined;
  const displayImageWidth = result?.image_width ?? previewImageDimensions?.width;
  const displayImageHeight = result?.image_height ?? previewImageDimensions?.height;
  const previewAspect = displayImageWidth && displayImageHeight ? { aspectRatio: `${displayImageWidth} / ${displayImageHeight}` } : undefined;
  const canRun = Boolean(prompt.trim()) && Boolean(selectedFile || imageUrl.trim()) && !isRunning;

  const selectFile = (file: File) => {
    const seq = (imageSelectionSeqRef.current += 1);
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = URL.createObjectURL(file);
    setSelectedFile(file);
    setSelectedFileName(file.name);
    setPreviewUrl(objectUrlRef.current);
    setPreviewImageDimensions(null);
    measurePreviewDimensions(objectUrlRef.current, seq);
    setImageUrl("");
    setResult(null);
    setSelectedRegionId("");
    setError(null);
  };

  const onImageUrlChange = (value: string) => {
    const seq = (imageSelectionSeqRef.current += 1);
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    setImageUrl(value);
    setSelectedFile(null);
    setSelectedFileName(null);
    setPreviewUrl(value.trim() || undefined);
    setPreviewImageDimensions(null);
    if (value.trim()) measurePreviewDimensions(value.trim(), seq);
    setResult(null);
    setSelectedRegionId("");
    setError(null);
  };

  const run = async () => {
    if (!canRun) {
      setError("Add an image source and a SAM3 prompt.");
      return;
    }

    setIsRunning(true);
    setError(null);
    try {
      const imageSource = selectedFile
        ? { image_object_key: (await uploadSearchImage(selectedFile)).image_object_key }
        : { image_url: imageUrl.trim() };
      const response = await segmentSam3({
        ...imageSource,
        prompt: prompt.trim(),
        confidence_threshold: confidenceThreshold,
        max_regions: maxRegions,
        include_masks: includeMasks,
      });
      setResult(response);
      setSelectedRegionId(response.regions[0]?.id ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "SAM3 request failed");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <main className="app-shell sam3-shell">
      <header className="topbar catalog-topbar">
        <Link className="brand-mark" to="/" aria-label="Back to workbench">
          <ArrowLeft size={22} />
        </Link>
        <div>
          <p className="eyebrow">Developer Tool</p>
          <h1>SAM3 playground</h1>
          <p className="sam3-api-note">API: {apiBaseUrl} · SAM3 via FastAPI model service</p>
        </div>
        <div className="topbar-actions">
          <Button type="button" onClick={run} disabled={!canRun}>
            {isRunning ? <Loader2 className="spin-icon" size={16} /> : <Play size={16} />}
            Run SAM3
          </Button>
        </div>
      </header>

      <section className="sam3-grid wrap" aria-label="SAM3 playground">
        <form className="sam3-panel sam3-controls" onSubmit={(event) => { event.preventDefault(); void run(); }}>
          <label className={`sam3-drop ${displayPreviewUrl ? "has-preview" : ""}`} htmlFor={fileInputId} style={previewAspect}>
            {displayPreviewUrl ? (
              <img src={displayPreviewUrl} alt={selectedFileName ?? "SAM3 input"} />
            ) : (
              <>
                <ImagePlus size={26} />
                <span>Upload image</span>
              </>
            )}
            <input
              id={fileInputId}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                if (file) selectFile(file);
                event.currentTarget.value = "";
              }}
            />
          </label>

          <label className="sam3-field">
            <span>Image URL</span>
            <input
              value={imageUrl}
              placeholder="https://..."
              onChange={(event) => onImageUrlChange(event.currentTarget.value)}
            />
          </label>

          <label className="sam3-field">
            <span>Prompt</span>
            <input
              value={prompt}
              onChange={(event) => setPrompt(event.currentTarget.value)}
              placeholder="floor tile, chair upholstery, wall panel"
            />
          </label>

          <div className="sam3-control-row">
            <label className="sam3-field">
              <span>Confidence</span>
              <input
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={confidenceThreshold}
                onChange={(event) => setConfidenceThreshold(Number(event.currentTarget.value))}
              />
            </label>
            <label className="sam3-field">
              <span>Max regions</span>
              <input
                type="number"
                min="1"
                max="100"
                value={maxRegions}
                onChange={(event) => setMaxRegions(Number(event.currentTarget.value))}
              />
            </label>
          </div>

          <label className="sam3-toggle">
            <input
              type="checkbox"
              checked={includeMasks}
              onChange={(event) => setIncludeMasks(event.currentTarget.checked)}
            />
            <span>Include masks</span>
          </label>

          {error ? <p className="form-error">{error}</p> : null}
        </form>

        <section className="sam3-panel">
          <div className="sam3-panel-head">
            <div>
              <p className="eyebrow">Raw SAM3</p>
              <h2>Response</h2>
            </div>
            <span>{result ? `${result.regions.length} regions` : "No run"}</span>
          </div>
          {result ? (
            <>
              <div className="sam3-table-wrap">
                <table className="sam3-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Score</th>
                      <th>Box xyxy</th>
                      <th>Mask</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.regions.map((region) => (
                      <tr key={region.id} className={region.id === selectedRegion?.id ? "active" : ""}>
                        <td>{region.id}</td>
                        <td>{region.score.toFixed(3)}</td>
                        <td>{region.box_xyxy.map((value) => Math.round(value)).join(", ")}</td>
                        <td>{region.mask ? `${region.mask.size.join("x")} / ${region.mask.counts.length}` : "none"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <pre className="sam3-json"><code>{JSON.stringify(result, null, 2)}</code></pre>
            </>
          ) : (
            <div className="sam3-empty">
              <Braces size={22} />
              <span>Raw JSON appears after a run.</span>
            </div>
          )}
        </section>
      </section>

      <section className="sam3-overlay-row wrap" aria-label="Overlay comparison">
        <div className="sam3-panel">
          <div className="sam3-panel-head">
            <div>
              <p className="eyebrow">Raw boxes</p>
              <h2>SAM3 coordinates</h2>
            </div>
            <span>{result ? `${result.image_width} x ${result.image_height}` : "pending"}</span>
          </div>
          <RawBoxStage
            previewUrl={displayPreviewUrl}
            result={result}
            imageWidth={displayImageWidth}
            imageHeight={displayImageHeight}
            selectedRegionId={selectedRegion?.id}
            onSelect={setSelectedRegionId}
          />
        </div>

        <div className="sam3-panel">
          <div className="sam3-panel-head">
            <div>
              <p className="eyebrow">App overlay</p>
              <h2>Studio projection</h2>
            </div>
            <span>{selectedRegion ? selectedRegion.confidence : "pending"}</span>
          </div>
          <ReferenceStage
            previewUrl={displayPreviewUrl}
            regions={regions}
            selectedRegionId={selectedRegion?.id ?? ""}
            imageWidth={displayImageWidth}
            imageHeight={displayImageHeight}
            onSelect={setSelectedRegionId}
          />
        </div>
      </section>
    </main>
  );

  function measurePreviewDimensions(src: string, seq: number) {
    measureImageDimensions(src)
      .then((dimensions) => {
        if (seq === imageSelectionSeqRef.current) setPreviewImageDimensions(dimensions);
      })
      .catch(() => {
        if (seq === imageSelectionSeqRef.current) setPreviewImageDimensions(null);
      });
  }
}

function RawBoxStage({
  previewUrl,
  result,
  imageWidth,
  imageHeight,
  selectedRegionId,
  onSelect,
}: {
  previewUrl?: string;
  result: RawSam3SegmentResponse | null;
  imageWidth?: number;
  imageHeight?: number;
  selectedRegionId?: string;
  onSelect: (regionId: string) => void;
}) {
  const aspect = imageWidth && imageHeight ? { aspectRatio: `${imageWidth} / ${imageHeight}` } : undefined;

  return (
    <div className="sam3-raw-stage" style={aspect}>
      {previewUrl ? <img src={previewUrl} alt="Raw SAM3 source" /> : <div className="stage-empty swatch-fallback" />}
      {result?.regions.map((region, index) => {
        const box = regionBox(region, result.image_width, result.image_height);
        return (
          <button
            key={region.id}
            type="button"
            className={`sam3-raw-region ${region.id === selectedRegionId ? "active" : ""}`}
            style={{
              left: `${box.left}%`,
              top: `${box.top}%`,
              width: `${box.width}%`,
              height: `${box.height}%`,
            }}
            onClick={() => onSelect(region.id)}
          >
            <span>{index + 1}</span>
          </button>
        );
      })}
    </div>
  );
}

function mapSam3Regions(result: RawSam3SegmentResponse): MaterialRegion[] {
  return result.regions.map((region, index) => ({
    id: region.id,
    label: `Region ${index + 1}`,
    material: region.prompt,
    confidence: confidenceLabel(region.score),
    box: regionBox(region, result.image_width, result.image_height),
    note: `SAM3 score ${region.score.toFixed(3)} for "${region.prompt}".`,
    searchIntent: result.prompt,
    included: true,
    score: region.score,
  }));
}

function regionBox(
  region: SegmentationRegionResponse,
  imageWidth: number,
  imageHeight: number,
): MaterialRegion["box"] {
  const [x0, y0, x1, y1] = region.box_xyxy;
  return {
    left: percent(x0, imageWidth),
    top: percent(y0, imageHeight),
    width: percent(x1 - x0, imageWidth),
    height: percent(y1 - y0, imageHeight),
  };
}

function percent(value: number, total: number): number {
  if (!total) return 0;
  return Math.max(0, Math.min(100, (value / total) * 100));
}

function confidenceLabel(score: number): MaterialRegion["confidence"] {
  if (score >= 0.8) return "High";
  if (score >= 0.55) return "Medium";
  return "Needs review";
}
