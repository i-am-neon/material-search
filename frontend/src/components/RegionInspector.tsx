import { CheckCircle2, Eye, Search } from "lucide-react";
import type { MaterialRegion, ProductMatch } from "../types";
import { ProductMatchCard } from "./ProductMatchCard";

type RegionInspectorProps = {
  region: MaterialRegion;
  matches: ProductMatch[];
  cartIds: string[];
  onToggleCart: (matchId: string) => void;
};

export function RegionInspector({ region, matches, cartIds, onToggleCart }: RegionInspectorProps) {
  return (
    <aside className="right-rail" aria-label="Selected material and matches">
      <section className="selected-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Selected Region</p>
            <h2>{region.label}</h2>
          </div>
          <span className={`confidence ${region.confidence === "High" ? "high" : ""}`}>
            {region.confidence}
          </span>
        </div>
        <p>{region.note}</p>
        <div className="intent-box">
          <Eye size={16} />
          <span>{region.searchIntent}</span>
        </div>
        <div className="metadata-grid">
          <span>Material read</span>
          <strong>{region.material}</strong>
          <span>Search mode</span>
          <strong>visual + catalog metadata</strong>
        </div>
      </section>

      <section className="matches-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Catalog Matches</p>
            <h2>Orderable materials</h2>
          </div>
          <button className="small-action" type="button">
            <Search size={15} />
            <span>Refine</span>
          </button>
        </div>

        <div className="match-list">
          {matches.map((match) => (
            <ProductMatchCard
              key={match.id}
              match={match}
              inCart={cartIds.includes(match.id)}
              onToggleCart={onToggleCart}
            />
          ))}
        </div>
      </section>

      <section className="cart-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Samples</p>
            <h2>Cart</h2>
          </div>
          <span className="cart-count">{cartIds.length}</span>
        </div>
        {cartIds.length ? (
          <div className="cart-ready">
            <CheckCircle2 size={17} />
            <span>Ready to review sample availability and checkout.</span>
          </div>
        ) : (
          <p className="muted-copy">Add strong options from any region to build a sample cart.</p>
        )}
        <button className="review-cart" disabled={!cartIds.length} type="button">
          Review cart
        </button>
      </section>
    </aside>
  );
}
