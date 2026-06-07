import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { IntakeScreen } from "./IntakeScreen";

const baseProps = {
  prompt: "",
  selectedFileName: undefined,
  previewUrl: undefined,
  isRunning: false,
  error: null,
  onPromptChange: vi.fn(),
  onPickFile: vi.fn(),
  onPickSample: vi.fn(),
  onRun: vi.fn(),
};

describe("IntakeScreen", () => {
  it("disables Read image until a file is chosen", () => {
    render(<IntakeScreen {...baseProps} />);
    expect(screen.getByRole("button", { name: /read image/i })).toBeDisabled();
  });

  it("enables and runs once a file is present", async () => {
    const onRun = vi.fn();
    render(<IntakeScreen {...baseProps} selectedFileName="room.png" onRun={onRun} />);
    const btn = screen.getByRole("button", { name: /read image/i });
    expect(btn).toBeEnabled();
    await userEvent.click(btn);
    expect(onRun).toHaveBeenCalledOnce();
  });

  it("shows an error when provided", () => {
    render(<IntakeScreen {...baseProps} error="Choose a reference image before running search." />);
    expect(screen.getByText(/choose a reference image/i)).toBeInTheDocument();
  });
});
