import type { Surface } from "../../hooks/useSearchRun";

type SurfaceSelectorProps = {
  surfaces: Surface[];
  selectedRegionId: string;
  onSelect: (regionId: string) => void;
};

export function SurfaceSelector({ surfaces, selectedRegionId, onSelect }: SurfaceSelectorProps) {
  return (
    <div className="surfaces" role="tablist" aria-label="Detected surfaces">
      {surfaces.map(({ region, matchCount, thumbUrl }) => (
        <button
          key={region.id}
          type="button"
          aria-selected={region.id === selectedRegionId}
          className={`surf ${region.id === selectedRegionId ? "active" : ""}`}
          onClick={() => onSelect(region.id)}
        >
          <span className={`surf-sw ${thumbUrl ? "" : "swatch-fallback"}`} style={thumbUrl ? { backgroundImage: `url(${thumbUrl})` } : undefined} />
          <span className="surf-label">{region.label}</span>
          <span className="surf-count">{matchCount}</span>
        </button>
      ))}
    </div>
  );
}
