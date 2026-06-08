import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ReferenceStage } from "./ReferenceStage";
import type { MaterialRegion } from "../../types";

const regions: MaterialRegion[] = [
  { id: "floor", label: "Floor", material: "tile", confidence: "High", box: { left: 5, top: 70, width: 90, height: 25 }, note: "", searchIntent: "", included: true },
  { id: "wall", label: "Wall", material: "paint", confidence: "Medium", box: { left: 2, top: 5, width: 60, height: 55 }, note: "", searchIntent: "", included: true },
];

describe("ReferenceStage", () => {
  it("marks the selected region and fires onSelect on click", async () => {
    const onSelect = vi.fn();
    render(<ReferenceStage previewUrl="room.png" regions={regions} selectedRegionId="floor" onSelect={onSelect} />);
    const wall = screen.getByRole("button", { name: /select wall/i });
    await userEvent.click(wall);
    expect(onSelect).toHaveBeenCalledWith("wall");
    expect(screen.getByRole("button", { name: /select floor/i })).toHaveClass("region sel");
    expect(screen.queryByText(/selected/i)).not.toBeInTheDocument();
  });
});
