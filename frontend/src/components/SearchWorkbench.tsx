import { Braces, Grid2X2, Layers3, ShoppingCart } from "lucide-react";
import { Link } from "react-router-dom";
import { useSearchRun, type UseSearchRunOptions } from "../hooks/useSearchRun";
import type { RunScenario } from "../types";
import { IntakeScreen } from "./IntakeScreen";
import { AnalysisReveal } from "./AnalysisReveal";
import { ProgressReveal } from "./ProgressReveal";
import { StudioScreen } from "./studio/StudioScreen";

type SearchWorkbenchProps = {
  initialScenario?: RunScenario;
  testTiming?: Pick<UseSearchRunOptions, "pollIntervalMs" | "minAnalyzeMs">;
};

export function SearchWorkbench({ initialScenario = "empty", testTiming }: SearchWorkbenchProps) {
  const run = useSearchRun({ initialScenario, ...testTiming });

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="mark">
          <span className="brand-glyph" aria-hidden="true"><Layers3 size={20} /></span>
          <span className="logo">Material<span className="slash"> / </span>Search</span>
        </div>
        <nav className="topnav">
          <Link className="active" to="/">Search</Link>
          <Link to="/catalog"><Grid2X2 size={15} /> Catalog</Link>
          <Link to="/sam3-playground"><Braces size={15} /> SAM3</Link>
          <span className="topnav-cart"><ShoppingCart size={15} /> {run.cartIds.length}</span>
        </nav>
      </header>

      {run.scenario === "empty" ? (
        <IntakeScreen
          prompt={run.prompt}
          selectedFileName={run.selectedFileName}
          previewUrl={run.previewUrl}
          isRunning={run.isRunning}
          error={run.error}
          onPromptChange={run.setPrompt}
          onPickFile={run.selectFile}
          onPickSample={run.selectSample}
          onRun={run.run}
        />
      ) : null}

      {run.scenario === "planning" || run.scenario === "matching" ? (
        <ProgressReveal
          snapshot={run.progress ?? { stage: "planning", surfaces: [], previewUrl: run.previewUrl }}
        />
      ) : null}

      {run.scenario === "failed" ? (
        <AnalysisReveal mode="failed" previewUrl={run.previewUrl} error={run.error} onRetry={run.run} onReset={() => window.location.reload()} />
      ) : null}

      {run.scenario === "complete" ? (
        <StudioScreen
          prompt={run.prompt}
          previewUrl={run.previewUrl}
          imageWidth={run.imageWidth}
          imageHeight={run.imageHeight}
          surfaces={run.surfaces}
          selectedRegion={run.selectedRegion}
          selectedRegionId={run.selectedRegionId}
          selectedMatches={run.selectedMatches}
          cartIds={run.cartIds}
          cartItems={run.cartItems}
          cartSurfaceCount={run.cartSurfaceCount}
          onSelectRegion={run.selectRegion}
          onToggleCart={run.toggleCart}
          onNewSearch={() => window.location.reload()}
          onOrder={() => {}}
        />
      ) : null}
    </main>
  );
}
