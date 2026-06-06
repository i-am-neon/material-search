import { ChevronDown, ImagePlus, Play, SlidersHorizontal } from "lucide-react";
import { defaultPrompt } from "../demoData";
import type { RunScenario } from "../types";

type SearchSetupProps = {
  scenario: RunScenario;
  onRun: () => void;
};

export function SearchSetup({ scenario, onRun }: SearchSetupProps) {
  const buttonLabel = scenario === "empty" ? "Run search" : "Rerun search";

  return (
    <aside className="left-rail" aria-label="Search setup">
      <button className="upload-button" type="button">
        <ImagePlus size={18} />
        <span>Replace image</span>
      </button>

      <label className="field-label" htmlFor="request">
        Intent
      </label>
      <textarea id="request" defaultValue={defaultPrompt} />

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

      <button className="primary-action" onClick={onRun} type="button">
        <Play size={18} fill="currentColor" />
        <span>{buttonLabel}</span>
      </button>
    </aside>
  );
}
