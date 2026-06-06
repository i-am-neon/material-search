import React from "react";
import {
  ChevronDown,
  ImagePlus,
  Loader2,
  Play,
  SlidersHorizontal,
  Upload,
  X,
} from "lucide-react";
import demoRoom from "../assets/demo-room.png";
import type { RunScenario } from "../types";

export type SampleImageOption = {
  id: string;
  name: string;
  src: string;
  filename: string;
};

type SearchSetupProps = {
  scenario: RunScenario;
  prompt: string;
  selectedFileName?: string;
  isRunning: boolean;
  error?: string | null;
  onPromptChange: (prompt: string) => void;
  onFileSelect: (file: File) => void;
  onSampleSelect: (sample: SampleImageOption) => void;
  onRun: () => void;
};

const sampleImages: SampleImageOption[] = [
  {
    id: "hospitality-lounge",
    name: "Hospitality lounge sample",
    src: demoRoom,
    filename: "hospitality-lounge-sample.png",
  },
];

export function SearchSetup({
  scenario,
  prompt,
  selectedFileName,
  isRunning,
  error,
  onPromptChange,
  onFileSelect,
  onSampleSelect,
  onRun,
}: SearchSetupProps) {
  const [isPickerOpen, setIsPickerOpen] = React.useState(false);
  const buttonLabel = isRunning ? "Running search" : scenario === "empty" ? "Run search" : "Rerun search";
  const canRun = Boolean(selectedFileName) && !isRunning;
  const fileInputId = "reference-image-upload";

  const handleFileSelect = (file: File) => {
    onFileSelect(file);
    setIsPickerOpen(false);
  };

  const handleSampleChoose = (sample: SampleImageOption) => {
    onSampleSelect(sample);
    setIsPickerOpen(false);
  };

  return (
    <aside className="left-rail" aria-label="Search setup">
      <button className="upload-button" onClick={() => setIsPickerOpen(true)} type="button">
        <ImagePlus size={18} />
        <span>{selectedFileName ?? "Choose image"}</span>
      </button>

      {isPickerOpen ? (
        <div
          aria-labelledby="image-picker-title"
          aria-modal="true"
          className="modal-backdrop"
          role="dialog"
        >
          <div className="image-picker-modal">
            <div className="modal-heading">
              <div>
                <p className="eyebrow">Reference Image</p>
                <h2 id="image-picker-title">Choose source</h2>
              </div>
              <button
                aria-label="Close image picker"
                className="icon-button"
                onClick={() => setIsPickerOpen(false)}
                type="button"
              >
                <X size={17} />
              </button>
            </div>

            <div className="sample-grid">
              {sampleImages.map((sample) => (
                <button
                  className="sample-option"
                  key={sample.id}
                  onClick={() => handleSampleChoose(sample)}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    handleSampleChoose(sample);
                  }}
                  onPointerDown={(event) => {
                    event.preventDefault();
                    handleSampleChoose(sample);
                  }}
                  type="button"
                >
                  <img src={sample.src} alt={sample.name} />
                  <span>{sample.name}</span>
                </button>
              ))}
            </div>

            <label className="own-upload-option" htmlFor={fileInputId}>
              <Upload size={18} />
              <span>Upload your own</span>
              <input
                accept="image/jpeg,image/png,image/webp"
                id={fileInputId}
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0];
                  if (file) {
                    handleFileSelect(file);
                  }
                  event.currentTarget.value = "";
                }}
                type="file"
              />
            </label>
          </div>
        </div>
      ) : null}

      <label className="field-label" htmlFor="request">
        Intent
      </label>
      <textarea
        id="request"
        value={prompt}
        onChange={(event) => onPromptChange(event.currentTarget.value)}
      />

      <div className="filter-block">
        <div className="filter-title">
          <SlidersHorizontal size={16} />
          <span>Search controls</span>
        </div>
        <button className="select-row" type="button">
          <span>Catalog scope</span>
          <strong>Interior finishes</strong>
          <ChevronDown size={16} />
        </button>
        <button className="select-row" type="button">
          <span>Material intent</span>
          <strong>Hospitality</strong>
          <ChevronDown size={16} />
        </button>
        <button className="select-row" type="button">
          <span>Result action</span>
          <strong>Add to cart</strong>
          <ChevronDown size={16} />
        </button>
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <button className="primary-action" disabled={!canRun} onClick={onRun} type="button">
        {isRunning ? <Loader2 className="spin-icon" size={18} /> : <Play size={18} fill="currentColor" />}
        <span>{buttonLabel}</span>
      </button>
    </aside>
  );
}
