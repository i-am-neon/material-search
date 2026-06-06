import { Sparkles } from "lucide-react";
import type { MaterialRegion, RunScenario } from "../types";
import demoRoom from "../assets/demo-room.png";

type RegionCanvasProps = {
  regions: MaterialRegion[];
  selectedRegionId: string;
  scenario: RunScenario;
  onSelectRegion: (regionId: string) => void;
};

export function RegionCanvas({ regions, selectedRegionId, scenario, onSelectRegion }: RegionCanvasProps) {
  const showRegions = scenario !== "empty" && scenario !== "planning" && scenario !== "failed";
  const includedRegions = regions.filter((region) => region.included);

  return (
    <section className="image-panel" aria-label="Detected material regions">
      <div className="image-toolbar">
        <div>
          <p className="eyebrow">Reference Image</p>
          <h2>Hospitality lounge sample</h2>
        </div>
        <div className="status-pill">
          <Sparkles size={16} />
          <span>{showRegions ? `${includedRegions.length} regions ready` : "analysis workspace"}</span>
        </div>
      </div>

      <div className={`image-canvas ${showRegions ? "has-regions" : ""}`}>
        <img src={demoRoom} alt="Contemporary lounge with multiple material surfaces" />
        {scenario === "planning" ? (
          <div className="canvas-overlay">
            <span>Reading surfaces, color, and material cues</span>
          </div>
        ) : null}
        {scenario === "failed" ? (
          <div className="canvas-overlay error">
            <span>Region detection needs another try</span>
          </div>
        ) : null}
        {showRegions
          ? includedRegions.map((region) => (
              <button
                key={region.id}
                className={`region-box ${region.id === selectedRegionId ? "selected" : ""}`}
                style={{
                  left: `${region.box.left}%`,
                  top: `${region.box.top}%`,
                  width: `${region.box.width}%`,
                  height: `${region.box.height}%`,
                }}
                onClick={() => onSelectRegion(region.id)}
                aria-label={`Select ${region.label}`}
                type="button"
              >
                <span>{region.label}</span>
              </button>
            ))
          : null}
      </div>

      <div className="region-strip" aria-label="Material regions">
        {showRegions ? (
          includedRegions.map((region) => (
            <button
              key={region.id}
              className={region.id === selectedRegionId ? "active" : ""}
              onClick={() => onSelectRegion(region.id)}
              type="button"
            >
              <span>{region.label}</span>
              <strong>{region.confidence}</strong>
            </button>
          ))
        ) : (
          <div className="strip-empty">
            Upload a reference image and run search to review detected material surfaces.
          </div>
        )}
      </div>
    </section>
  );
}
