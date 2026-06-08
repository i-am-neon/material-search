import React from "react";
import { ArrowRight, ImagePlus, Loader2, Upload } from "lucide-react";
import { sampleImages, type SampleImageOption } from "../samples";

type IntakeScreenProps = {
  prompt: string;
  selectedFileName?: string;
  previewUrl?: string;
  isRunning: boolean;
  error?: string | null;
  onPromptChange: (value: string) => void;
  onPickFile: (file: File) => void;
  onPickSample: (sample: SampleImageOption) => void;
  onRun: () => void;
};

export function IntakeScreen({
  prompt,
  selectedFileName,
  previewUrl,
  isRunning,
  error,
  onPromptChange,
  onPickFile,
  onPickSample,
  onRun,
}: IntakeScreenProps) {
  const fileInputId = React.useId();
  const canRun = Boolean(selectedFileName) && !isRunning;

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
        <label className="dz-canvas" htmlFor={fileInputId}>
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

        {sampleImages.length ? (
          <button
            type="button"
            className="dz-sample"
            onClick={() => onPickSample(sampleImages[0])}
          >
            <Upload size={14} />
            <span>or start with the {sampleImages[0].name.toLowerCase()} sample</span>
          </button>
        ) : null}

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
