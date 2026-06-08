import React from "react";
import { ArrowRight, ImagePlus, Loader2 } from "lucide-react";

type IntakeScreenProps = {
  prompt: string;
  selectedFileName?: string;
  previewUrl?: string;
  imageWidth?: number;
  imageHeight?: number;
  isRunning: boolean;
  error?: string | null;
  onPromptChange: (value: string) => void;
  onPickFile: (file: File) => void;
  onRun: () => void;
};

export function IntakeScreen({
  prompt,
  selectedFileName,
  previewUrl,
  imageWidth,
  imageHeight,
  isRunning,
  error,
  onPromptChange,
  onPickFile,
  onRun,
}: IntakeScreenProps) {
  const fileInputId = React.useId();
  const canRun = Boolean(selectedFileName) && !isRunning;
  const previewAspect = imageWidth && imageHeight ? { aspectRatio: `${imageWidth} / ${imageHeight}` } : undefined;

  return (
    <section className="intake-body wrap" aria-label="New material search">
      <div className="intake-copy">
        <p className="eyebrow">Visual material sourcing</p>
        <h1 className="intake-headline">
          Source it
          <br />
          from an <span>image</span>.
        </h1>
        <p className="intake-lede">
          Drop in a room, a surface, an inspiration. We read every material in it — and match it to
          what you can actually sample.
        </p>
        <div className="pipeline-note">
          <span><b>SAM&nbsp;3</b> segmentation</span>
          <span className="dot">·</span>
          <span><b>Vector</b> catalog match</span>
          <span className="dot">·</span>
          <span><b>600+</b> materials</span>
        </div>
      </div>

      <div className="intake-card">
        <label className={`dz-canvas ${previewUrl ? "has-preview" : ""}`} htmlFor={fileInputId} style={previewAspect}>
          {previewUrl ? (
            <img className="dz-preview" src={previewUrl} alt={selectedFileName ?? "Reference"} />
          ) : (
            <>
              <span className="dz-icon"><ImagePlus size={22} /></span>
              <span className="dz-title">Drop a reference image</span>
              <span className="dz-sub">or browse — JPG, PNG, WebP</span>
            </>
          )}
          <input
            id={fileInputId}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => {
              const file = e.currentTarget.files?.[0];
              if (file) onPickFile(file);
              e.currentTarget.value = "";
            }}
          />
        </label>

        <div className="dz-prompt">
          <input
            aria-label="Search intent"
            value={prompt}
            placeholder="What are you sourcing?"
            onChange={(e) => onPromptChange(e.currentTarget.value)}
          />
          <button type="button" className="ui-button ui-button-default ui-button-size-default" disabled={!canRun} onClick={onRun}>
            {isRunning ? <Loader2 className="spin-icon" size={15} /> : null}
            <span>Read image</span>
            {!isRunning ? <ArrowRight size={15} /> : null}
          </button>
        </div>

        {error ? <p className="form-error">{error}</p> : null}
      </div>
    </section>
  );
}
