import { ArrowRight } from "lucide-react";
import type { ProductMatch } from "../../types";

type SpecificationTrayProps = {
  items: ProductMatch[];
  surfaceCount: number;
  onOrder: () => void;
};

export function SpecificationTray({ items, surfaceCount, onOrder }: SpecificationTrayProps) {
  const surfaceWord = surfaceCount === 1 ? "surface" : "surfaces";
  const materialWord = items.length === 1 ? "material" : "materials";
  return (
    <div className="tray">
      <div className="tray-in wrap">
        <div className="tray-left">
          <span className="tray-lbl">Specification</span>
          <div className="tray-sw">
            {items.slice(0, 5).map((m) => (
              <span
                key={m.id}
                className={`tray-chip ${m.item.image_url ? "" : "swatch-fallback"}`}
                style={m.item.image_url ? { backgroundImage: `url(${m.item.image_url})` } : undefined}
              />
            ))}
          </div>
          <span className="tray-count">
            {`${items.length} ${materialWord} across ${surfaceCount} ${surfaceWord}`}
          </span>
        </div>
        <button type="button" className="ui-button ui-button-default ui-button-size-default" disabled={!items.length} onClick={onOrder}>
          <span>Order samples</span>
          <ArrowRight size={15} />
        </button>
      </div>
    </div>
  );
}
