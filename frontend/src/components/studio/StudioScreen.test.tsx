import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { StudioScreen } from "./StudioScreen";
import { regions, matchesByRegion } from "../../demoData";
import type { Surface } from "../../hooks/useSearchRun";
import demoRoom from "../../assets/demo-room.png";

const surfaces: Surface[] = regions.map((region) => ({
  region,
  matchCount: matchesByRegion[region.id]?.length ?? 0,
  thumbUrl: matchesByRegion[region.id]?.[0]?.item.image_url ?? undefined,
}));

function props(overrides = {}) {
  return {
    prompt: "warm matte floor",
    previewUrl: demoRoom,
    surfaces,
    selectedRegion: regions[0],
    selectedRegionId: regions[0].id,
    selectedMatches: matchesByRegion[regions[0].id],
    cartIds: [],
    cartItems: [],
    cartSurfaceCount: 0,
    onSelectRegion: vi.fn(),
    onToggleCart: vi.fn(),
    onNewSearch: vi.fn(),
    onOrder: vi.fn(),
    ...overrides,
  };
}

describe("StudioScreen", () => {
  it("shows intent, surfaces, and matches for the selected region", () => {
    render(<StudioScreen {...props()} />);
    expect(screen.getByText(/warm matte floor/i)).toBeInTheDocument();
    expect(screen.getByText(`${surfaces.length} surfaces detected`)).toBeInTheDocument();
    expect(screen.queryByText(/avg confidence/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /select aggregate floor/i })).toBeInTheDocument();
    expect(screen.getAllByText(/add to specification|in specification/i).length).toBeGreaterThan(0);
  });

  it("fires onNewSearch from the sub-header", async () => {
    const onNewSearch = vi.fn();
    render(<StudioScreen {...props({ onNewSearch })} />);
    await userEvent.click(screen.getByRole("button", { name: /new search/i }));
    expect(onNewSearch).toHaveBeenCalledOnce();
  });
});
