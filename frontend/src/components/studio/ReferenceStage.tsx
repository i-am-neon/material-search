import type { MaterialRegion } from "../../types";

type ReferenceStageProps = {
  previewUrl?: string;
  regions: MaterialRegion[];
  selectedRegionId: string;
  imageWidth?: number;
  imageHeight?: number;
  onSelect: (regionId: string) => void;
};

export function ReferenceStage({
  previewUrl,
  regions,
  selectedRegionId,
  imageWidth,
  imageHeight,
  onSelect,
}: ReferenceStageProps) {
  const aspect = imageWidth && imageHeight ? { aspectRatio: `${imageWidth} / ${imageHeight}` } : undefined;
  return (
    <div className="ref-col">
      <div className="ref-head">
        <h2>Your reference</h2>
        <span className="ref-meta">tap a surface</span>
      </div>
      <div className="stage" style={aspect}>
        {previewUrl ? <img src={previewUrl} alt="Reference" /> : <div className="stage-empty swatch-fallback" />}
        {regions
          .filter((r) => r.included)
          .map((region) => {
            const flipTag = region.box.left + region.box.width / 2 > 50;
            return (
              <button
                key={region.id}
                type="button"
                className={`region ${region.id === selectedRegionId ? "sel" : ""}`}
                style={{
                  left: `${region.box.left}%`,
                  top: `${region.box.top}%`,
                  width: `${region.box.width}%`,
                  height: `${region.box.height}%`,
                }}
                onClick={() => onSelect(region.id)}
                aria-label={`Select ${region.label}`}
              >
                <span className={`tag ${flipTag ? "flip" : ""}`}>{region.label}</span>
              </button>
            );
          })}
      </div>
    </div>
  );
}
