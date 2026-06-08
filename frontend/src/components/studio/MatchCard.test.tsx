import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MatchCard } from "./MatchCard";
import type { ProductMatch } from "../../types";

const match: ProductMatch = {
  id: "floor-oak",
  fit: "Best fit",
  similarity: 0.96,
  item: { manufacturer: "Listone Giordano", name: "Heritage Oak", material_family: "wood", image_object_key: "oak.png", image_url: "http://img/oak.png", metadata: {} },
  reasons: ["Matches the floor surface", "Orderable catalog item"],
};

describe("MatchCard", () => {
  it("renders brand, name, family and toggles cart", async () => {
    const onToggleCart = vi.fn();
    render(<MatchCard match={match} inCart={false} onToggleCart={onToggleCart} />);
    expect(screen.getByText("Listone Giordano")).toBeInTheDocument();
    expect(screen.getByText("Heritage Oak")).toBeInTheDocument();
    expect(screen.getByText("wood")).toBeInTheDocument();
    expect(screen.queryByText("96%")).not.toBeInTheDocument();
    expect(screen.queryByText("Matches the floor surface")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /add to specification/i }));
    expect(onToggleCart).toHaveBeenCalledWith("floor-oak");
  });

  it("shows in-spec state", () => {
    render(<MatchCard match={match} inCart onToggleCart={vi.fn()} />);
    expect(screen.getByRole("button", { name: /in specification/i })).toBeInTheDocument();
  });
});
