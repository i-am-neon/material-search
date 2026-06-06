import { Check, ShoppingCart } from "lucide-react";
import { formatFamily } from "../demoData";
import type { ProductMatch } from "../types";

type ProductMatchCardProps = {
  match: ProductMatch;
  inCart: boolean;
  onToggleCart: (matchId: string) => void;
};

export function ProductMatchCard({ match, inCart, onToggleCart }: ProductMatchCardProps) {
  const { item } = match;
  const sourceUrl = item.metadata.source_url;
  const family = formatFamily(item.material_family ?? "uncategorized");
  const colorway = item.metadata.colorway;

  return (
    <article className="match-card">
      <a className="match-image" href={sourceUrl} target="_blank" rel="noreferrer">
        {item.image_url ? <img src={item.image_url} alt={`${item.manufacturer} ${item.name}`} /> : null}
      </a>
      <div className="match-copy">
        <div className="match-heading">
          <span className="fit-label">{match.fit}</span>
          <h3>{item.name}</h3>
          <p>{item.manufacturer}</p>
        </div>
        <div className="match-tags">
          <span>{family}</span>
          {colorway ? <span>{colorway}</span> : null}
        </div>
        <ul className="reason-list">
          {match.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </div>
      <button
        className={`cart-action ${inCart ? "in-cart" : ""}`}
        onClick={() => onToggleCart(match.id)}
        type="button"
      >
        {inCart ? <Check size={16} /> : <ShoppingCart size={16} />}
        <span>{inCart ? "In cart" : "Add to cart"}</span>
      </button>
    </article>
  );
}
