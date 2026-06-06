import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SpecificationTray } from "./SpecificationTray";
import { matchesByRegion } from "../../demoData";

describe("SpecificationTray", () => {
  it("summarizes collected materials across surfaces", () => {
    const items = [matchesByRegion["terrazzo-floor"][0], matchesByRegion["walnut-panels"][0]];
    render(<SpecificationTray items={items} surfaceCount={2} onOrder={vi.fn()} />);
    expect(screen.getByText(/2 materials across 2 surfaces/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /order samples/i })).toBeEnabled();
  });

  it("disables ordering when empty", () => {
    render(<SpecificationTray items={[]} surfaceCount={0} onOrder={vi.fn()} />);
    expect(screen.getByRole("button", { name: /order samples/i })).toBeDisabled();
  });
});
