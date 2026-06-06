import React from "react";
import { Download, Grid2X2, Layers3, ShoppingCart } from "lucide-react";
import { Link } from "react-router-dom";
import { getRunStages, matchesByRegion, regions } from "../demoData";
import type { RunScenario } from "../types";
import { RegionCanvas } from "./RegionCanvas";
import { RegionInspector } from "./RegionInspector";
import { RunTimeline } from "./RunTimeline";
import { SearchSetup } from "./SearchSetup";

type SearchWorkbenchProps = {
  initialScenario?: RunScenario;
};

export function SearchWorkbench({ initialScenario = "complete" }: SearchWorkbenchProps) {
  const [scenario, setScenario] = React.useState<RunScenario>(initialScenario);
  const [selectedRegionId, setSelectedRegionId] = React.useState(regions[0].id);
  const [cartIds, setCartIds] = React.useState<string[]>([]);
  const selectedRegion = regions.find((region) => region.id === selectedRegionId) ?? regions[0];
  const selectedMatches = scenario === "complete" ? matchesByRegion[selectedRegion.id] : [];
  const stageLabel = scenario === "empty" ? "NEW RUN" : scenario === "failed" ? "RUN-2406-F" : "RUN-2406";

  const handleToggleCart = (matchId: string) => {
    setCartIds((current) =>
      current.includes(matchId) ? current.filter((id) => id !== matchId) : [...current, matchId],
    );
  };

  const handleRun = () => {
    setScenario("complete");
    setSelectedRegionId(regions[0].id);
  };

  return (
    <main className="app-shell">
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

      <section className="workspace-grid">
        <SearchSetup scenario={scenario} onRun={handleRun} />

        <div className="center-stack">
          <RunTimeline stages={getRunStages(scenario)} runLabel={stageLabel} />
          <RegionCanvas
            regions={regions}
            selectedRegionId={selectedRegionId}
            scenario={scenario}
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
    </main>
  );
}
