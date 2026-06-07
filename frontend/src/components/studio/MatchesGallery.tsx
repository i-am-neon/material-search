import { MatchCard } from "./MatchCard";
import type { ProductMatch } from "../../types";

type MatchesGalleryProps = {
  surfaceLabel?: string;
  matches: ProductMatch[];
  cartIds: string[];
  onToggleCart: (matchId: string) => void;
};

export function MatchesGallery({ surfaceLabel, matches, cartIds, onToggleCart }: MatchesGalleryProps) {
  return (
    <div className="match-col">
      <div className="matches-head">
        <h2>Matching the <span>{surfaceLabel ?? "surface"}</span></h2>
        <span className="matches-ct">{matches.length} materials · ranked by similarity</span>
      </div>
      {matches.length ? (
        <div className="match-grid">
          {matches.map((match) => (
            <MatchCard key={match.id} match={match} inCart={cartIds.includes(match.id)} onToggleCart={onToggleCart} />
          ))}
        </div>
      ) : (
        <p className="muted-copy">No catalog matches for this surface yet.</p>
      )}
    </div>
  );
}
