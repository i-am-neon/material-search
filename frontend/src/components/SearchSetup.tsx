import React from "react";
import {
  ArrowRight,
  ImagePlus,
  Loader2,
  Play,
  Upload,
} from "lucide-react";
import demoRoom from "../assets/demo-room.png";
import type { RunScenario } from "../types";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";
import { Textarea } from "./ui/textarea";

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
  previewUrl?: string;
  isRunning: boolean;
  error?: string | null;
  layout?: "page" | "rail";
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
  previewUrl,
  isRunning,
  error,
  layout = "rail",
  onPromptChange,
  onFileSelect,
  onSampleSelect,
  onRun,
}: SearchSetupProps) {
  const [isPickerOpen, setIsPickerOpen] = React.useState(false);
  const controlId = React.useId();
  const buttonLabel =
    isRunning ? "Running search" : scenario === "empty" ? "Start material search" : "Rerun search";
  const canRun = Boolean(selectedFileName) && !isRunning;
  const fileInputId = `${controlId}-reference-image-upload`;
  const promptInputId = `${controlId}-request`;
  const queryTitleId = `${controlId}-query-title`;
  const imageTitleId = `${controlId}-image-title`;
  const isPage = layout === "page";

  const handleFileSelect = (file: File) => {
    onFileSelect(file);
    setIsPickerOpen(false);
  };

  const handleSampleChoose = (sample: SampleImageOption) => {
    onSampleSelect(sample);
    setIsPickerOpen(false);
  };

  const imagePicker = (
    <Dialog open={isPickerOpen} onOpenChange={setIsPickerOpen}>
      <DialogTrigger asChild>
        {isPage ? (
          <Button className="intake-upload-trigger" variant="outline" type="button">
            <ImagePlus size={18} />
            <span>{selectedFileName ? "Change image" : "Choose image"}</span>
          </Button>
        ) : (
          <Button className="upload-button" variant="outline" type="button">
            <ImagePlus size={18} />
            <span>{selectedFileName ?? "Choose image"}</span>
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="image-picker-modal">
        <DialogHeader>
          <p className="eyebrow">Reference Image</p>
          <DialogTitle>Choose source</DialogTitle>
          <DialogDescription>
            Upload a room image or start with the hospitality lounge sample.
          </DialogDescription>
        </DialogHeader>

        <div className="sample-grid">
          {sampleImages.map((sample) => (
            <button
              className="sample-option"
              key={sample.id}
              onClick={() => handleSampleChoose(sample)}
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
      </DialogContent>
    </Dialog>
  );

  if (isPage) {
    return (
      <section className="intake-screen" aria-label="New material search">
        <div className="intake-copy">
          <p className="eyebrow">New Search</p>
          <h1>Describe the material direction and add a reference image.</h1>
          <p>
            The first pass will identify orderable surfaces from the uploaded room image, then move
            into region review and catalog matching.
          </p>
        </div>

        <div className="intake-grid">
          <section className="intake-panel intake-query-panel" aria-labelledby={queryTitleId}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">Search Intent</p>
                <h2 id={queryTitleId}>What should the matcher look for?</h2>
              </div>
            </div>
            <Textarea
              id={promptInputId}
              className="intake-textarea"
              aria-labelledby={queryTitleId}
              value={prompt}
              onChange={(event) => onPromptChange(event.currentTarget.value)}
            />
            <div className="intake-suggestion-row" aria-label="Suggested search controls">
              <span>Interior finishes</span>
              <span>Hospitality</span>
              <span>Add to cart</span>
            </div>
          </section>

          <section className="intake-panel intake-image-panel" aria-labelledby={imageTitleId}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">Reference Image</p>
                <h2 id={imageTitleId}>Upload the room or product context.</h2>
              </div>
            </div>
            <div className={`intake-preview ${previewUrl ? "has-image" : ""}`}>
              {previewUrl ? (
                <img src={previewUrl} alt={selectedFileName ?? "Selected reference"} />
              ) : (
                <div>
                  <ImagePlus size={28} />
                  <span>No image selected</span>
                </div>
              )}
            </div>
            <div className="intake-image-actions">{imagePicker}</div>
            {selectedFileName ? <p className="selected-file-name">{selectedFileName}</p> : null}
          </section>
        </div>

        {error ? <p className="form-error intake-error">{error}</p> : null}

        <div className="intake-submit-row">
          <Button
            className="primary-action intake-primary-action"
            disabled={!canRun}
            onClick={onRun}
            type="button"
          >
            {isRunning ? <Loader2 className="spin-icon" size={18} /> : <ArrowRight size={18} />}
            <span>{buttonLabel}</span>
          </Button>
        </div>
      </section>
    );
  }

  return (
    <aside className="left-rail" aria-label="Search setup">
      {imagePicker}

      <label className="field-label" htmlFor={promptInputId}>
        Intent
      </label>
      <Textarea
        id={promptInputId}
        value={prompt}
        onChange={(event) => onPromptChange(event.currentTarget.value)}
      />

      {error ? <p className="form-error">{error}</p> : null}

      <Button className="primary-action" disabled={!canRun} onClick={onRun} type="button">
        {isRunning ? <Loader2 className="spin-icon" size={18} /> : <Play size={18} fill="currentColor" />}
        <span>{buttonLabel}</span>
      </Button>
    </aside>
  );
}
