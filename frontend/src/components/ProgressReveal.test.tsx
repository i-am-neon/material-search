import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProgressReveal } from "./ProgressReveal";
import { completeFrame, matchingFrame, planningFrame } from "../progressDemo";

describe("ProgressReveal", () => {
  it("shows the understanding step active while planning, before intent resolves", () => {
    render(<ProgressReveal snapshot={planningFrame} />);
    expect(screen.getByText(/understanding your request/i)).toBeInTheDocument();
    expect(screen.getByText(/reading your reference image and prompt/i)).toBeInTheDocument();
  });

  it("reports matching progress with a populated progressbar", () => {
    render(<ProgressReveal snapshot={matchingFrame} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "2");
    expect(bar).toHaveAttribute("aria-valuemax", String(matchingFrame.surfaces.length));
    // One box per resolved surface is drawn on the image.
    expect(screen.getAllByText(matchingFrame.surfaces[0].label).length).toBeGreaterThan(0);
  });

  it("marks the run ready once complete", () => {
    render(<ProgressReveal snapshot={completeFrame} />);
    expect(screen.getByText(/opening your studio view/i)).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`matched ${completeFrame.surfaces.length} surfaces`, "i")),
    ).toBeInTheDocument();
  });
});
