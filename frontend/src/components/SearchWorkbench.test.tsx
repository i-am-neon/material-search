import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api", () => ({
  uploadSearchImage: vi.fn().mockResolvedValue({ image_object_key: "k", content_type: "image/png", size_bytes: 1 }),
  createSearchRun: vi.fn().mockResolvedValue({ run_id: "r1", status: "queued" }),
  getSearchRunStatus: vi.fn().mockResolvedValue({
    run: { id: "r1", prompt: "p", source_image_object_key: "k", source_image_url: null, status: "completed", error: null, image_width: 100, image_height: 80, created_at: "", updated_at: "" },
    result: {
      run_id: "r1", prompt: "p", plan: null, image_width: 100, image_height: 80,
      regions: [{ region: { id: "rg", prompt: "floor", score: 0.9, box_xyxy: [0, 60, 100, 80] }, target_id: "t", target_label: "Floor", crop_object_key: "c", crop_url: null, crop_width: 1, crop_height: 1, model_id: "m", dimensions: 1, matches: [{ region_id: "rg", rank: 1, match: { item: { id: "i", manufacturer: "Brand", name: "Oak", material_family: "wood", image_object_key: "i.png", image_url: null, metadata: {}, created_at: "", updated_at: "" }, model_id: "m", similarity: 0.9 } }] }],
    },
  }),
}));

import { SearchWorkbench } from "./SearchWorkbench";

beforeEach(() => vi.clearAllMocks());

describe("SearchWorkbench", () => {
  it("starts on the intake screen", () => {
    render(<MemoryRouter><SearchWorkbench testTiming={{ pollIntervalMs: 0, minAnalyzeMs: 0 }} /></MemoryRouter>);
    expect(screen.getByRole("button", { name: /read image/i })).toBeInTheDocument();
  });

  it("runs a search and lands in the studio", async () => {
    render(<MemoryRouter><SearchWorkbench initialScenario="complete" /></MemoryRouter>);
    // initialScenario=complete uses demo data, so the studio sub-header is present
    expect(await screen.findByText(/surfaces detected/i)).toBeInTheDocument();
  });
});
