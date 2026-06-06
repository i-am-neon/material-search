import { Check, Plus } from "lucide-react";
import { formatFamily } from "../../demoData";
import type { ProductMatch } from "../../types";

type MatchCardProps = {
  match: ProductMatch;
  inCart: boolean;
  onToggleCart: (matchId: string) => void;
};

export function MatchCard({ match, inCart, onToggleCart }: MatchCardProps) {
  const { item } = match;
  const family = formatFamily(item.material_family ?? "uncategorized");
  const why = match.reasons[0];
  const label = inCart ? "In specification" : "Add to specification";

  return (
    <article className="mcard">
      <div className={`mswatch ${item.image_url ? "" : "swatch-fallback"}`}>
        {item.image_url ? <img src={item.image_url} alt={`${item.manufacturer} ${item.name}`} /> : null}
        {typeof match.similarity === "number" ? (
          <span className="sim">{Math.round(match.similarity * 100)}%</span>
        ) : null}
      </div>
      <div className="mbody">
        <div className="brand">{item.manufacturer}</div>
        <h4>{item.name}</h4>
        {why ? <p className="why">{why}</p> : null}
        <div className="madd">
          <span className="sample-note">Sample · {family}</span>
          <button
            type="button"
            className={`plus ${inCart ? "added" : ""}`}
            aria-label={label}
            title={label}
            onClick={() => onToggleCart(match.id)}
          >
            {inCart ? <Check size={16} /> : <Plus size={16} />}
          </button>
        </div>
      </div>
    </article>
  );
}
