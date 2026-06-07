import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnalysisReveal } from "./AnalysisReveal";

describe("AnalysisReveal", () => {
  it("shows scanning copy while analyzing", () => {
    render(<AnalysisReveal mode="analyzing" previewUrl="x.png" error={null} onRetry={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByText(/reading the image/i)).toBeInTheDocument();
  });

  it("shows error + retry when failed", async () => {
    const onRetry = vi.fn();
    render(<AnalysisReveal mode="failed" previewUrl="x.png" error="segmenter timed out" onRetry={onRetry} onReset={vi.fn()} />);
    expect(screen.getByText(/segmenter timed out/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
