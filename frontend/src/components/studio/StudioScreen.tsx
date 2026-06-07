import { ArrowLeft } from "lucide-react";
import type { MaterialRegion, ProductMatch } from "../../types";
import type { Surface } from "../../hooks/useSearchRun";
import { ReferenceStage } from "./ReferenceStage";
import { SurfaceSelector } from "./SurfaceSelector";
import { MatchesGallery } from "./MatchesGallery";
import { SpecificationTray } from "./SpecificationTray";

type StudioScreenProps = {
  prompt: string;
  previewUrl?: string;
  imageWidth?: number;
  imageHeight?: number;
  surfaces: Surface[];
  selectedRegion?: MaterialRegion;
  selectedRegionId: string;
  selectedMatches: ProductMatch[];
  cartIds: string[];
  cartItems: ProductMatch[];
  cartSurfaceCount: number;
  onSelectRegion: (regionId: string) => void;
  onToggleCart: (matchId: string) => void;
  onNewSearch: () => void;
  onOrder: () => void;
};

export function StudioScreen({
  prompt,
  previewUrl,
  imageWidth,
  imageHeight,
  surfaces,
  selectedRegion,
  selectedRegionId,
  selectedMatches,
  cartIds,
  cartItems,
  cartSurfaceCount,
  onSelectRegion,
  onToggleCart,
  onNewSearch,
  onOrder,
}: StudioScreenProps) {
  const avgConfidence = surfaces.length
    ? surfaces.reduce((sum, s) => sum + (s.region.score ?? 0), 0) / surfaces.length
    : 0;

  return (
    <section className="studio" aria-label="Material studio">
      <div className="studio-sub">
        <div className="studio-intent">
          <button type="button" className="studio-back" onClick={onNewSearch}>
            <ArrowLeft size={14} /> New search
          </button>
          <span className="chip">Sourcing for <span className="chip-q">"{prompt}"</span></span>
        </div>
        <div className="studio-meta">
          {surfaces.length} surfaces detected{avgConfidence ? ` · ${avgConfidence.toFixed(2)} avg confidence` : ""}
        </div>
      </div>

      <div className="studio-grid wrap">
        <ReferenceStage
          previewUrl={previewUrl}
          regions={surfaces.map((s) => s.region)}
          selectedRegionId={selectedRegionId}
          imageWidth={imageWidth}
          imageHeight={imageHeight}
          onSelect={onSelectRegion}
        />
        <div className="studio-right">
          <MatchesGallery
            surfaceLabel={selectedRegion?.label}
            matches={selectedMatches}
            cartIds={cartIds}
            onToggleCart={onToggleCart}
          />
        </div>
      </div>
      <div className="studio-grid wrap studio-selector-row">
        <SurfaceSelector surfaces={surfaces} selectedRegionId={selectedRegionId} onSelect={onSelectRegion} />
        <div />
      </div>

      <SpecificationTray items={cartItems} surfaceCount={cartSurfaceCount} onOrder={onOrder} />
    </section>
  );
}
