import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SurfaceSelector } from "./SurfaceSelector";
import type { Surface } from "../../hooks/useSearchRun";

const surfaces: Surface[] = [
  { region: { id: "floor", label: "Floor", material: "", confidence: "High", box: { left: 0, top: 0, width: 1, height: 1 }, note: "", searchIntent: "", included: true }, matchCount: 12 },
  { region: { id: "wall", label: "Wall", material: "", confidence: "Medium", box: { left: 0, top: 0, width: 1, height: 1 }, note: "", searchIntent: "", included: true }, matchCount: 9 },
];

describe("SurfaceSelector", () => {
  it("renders each surface with its count and selects on click", async () => {
    const onSelect = vi.fn();
    render(<SurfaceSelector surfaces={surfaces} selectedRegionId="floor" onSelect={onSelect} />);
    expect(screen.getByText("Floor")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /wall/i }));
    expect(onSelect).toHaveBeenCalledWith("wall");
  });
});
