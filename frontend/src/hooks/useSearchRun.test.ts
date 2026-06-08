import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useSearchRun } from "./useSearchRun";
import type { SearchRunStatusResponse, SegmentMatchResponse } from "../api";

vi.mock("../api", () => ({
  uploadSearchImage: vi.fn(),
  createSearchRun: vi.fn(),
  getSearchRunStatus: vi.fn(),
}));

import { createSearchRun, getSearchRunStatus, uploadSearchImage } from "../api";

const result_: SegmentMatchResponse = {
  run_id: "run-123",
  prompt: "warm matte floor tile",
  plan: { user_intent_summary: "warm floor", avoid: [], targets: [] },
  image_width: 1000,
  image_height: 800,
  regions: [
    {
      result_region_id: "r-floor",
      region: { id: "sam-1", prompt: "floor", score: 0.96, box_xyxy: [0, 600, 1000, 800] },
      target_id: "t1",
      target_label: "Floor",
      crop_object_key: "crop1",
      crop_url: null,
      crop_width: 100,
      crop_height: 100,
      model_id: "m",
      dimensions: 512,
      matches: [
        { region_id: "r-floor", rank: 1, match: { item: item("oak", "Heritage Oak"), model_id: "m", similarity: 0.96 } },
        { region_id: "r-floor", rank: 2, match: { item: item("trav", "Travertine"), model_id: "m", similarity: 0.91 } },
      ],
    },
    {
      result_region_id: "r-wall",
      region: { id: "sam-2", prompt: "wall", score: 0.82, box_xyxy: [0, 0, 600, 500] },
      target_id: "t2",
      target_label: "Wall",
      crop_object_key: "crop2",
      crop_url: null,
      crop_width: 100,
      crop_height: 100,
      model_id: "m",
      dimensions: 512,
      matches: [
        { region_id: "r-wall", rank: 1, match: { item: item("linen", "Linen"), model_id: "m", similarity: 0.88 } },
      ],
    },
  ],
};

function item(id: string, name: string) {
  return {
    id,
    manufacturer: "Brand",
    name,
    material_family: "wood",
    image_object_key: `${id}.png`,
    image_url: `http://img/${id}.png`,
    metadata: {},
    created_at: "",
    updated_at: "",
  };
}

const completed: SearchRunStatusResponse = {
  run: { id: "run-123", prompt: "p", source_image_object_key: "k", source_image_url: null, status: "completed", error: null, image_width: 1000, image_height: 800, created_at: "", updated_at: "" },
  result: result_,
};

const fast = { pollIntervalMs: 0, minAnalyzeMs: 0 };

beforeEach(() => {
  vi.mocked(uploadSearchImage).mockReset();
  vi.mocked(createSearchRun).mockReset();
  vi.mocked(getSearchRunStatus).mockReset();
  vi.mocked(uploadSearchImage).mockResolvedValue({ image_object_key: "k", content_type: "image/png", size_bytes: 1 });
  vi.mocked(createSearchRun).mockResolvedValue({ run_id: "run-123", status: "queued" });
  vi.mocked(getSearchRunStatus).mockResolvedValue(completed);
});

function pngFile() {
  return new File([new Uint8Array([1, 2, 3])], "room.png", { type: "image/png" });
}

describe("useSearchRun", () => {
  it("starts empty", () => {
    const { result } = renderHook(() => useSearchRun(fast));
    expect(result.current.scenario).toBe("empty");
    expect(result.current.prompt).toBe("");
    expect(result.current.previewUrl).toBeUndefined();
  });

  it("selectFile sets preview + filename", () => {
    const { result } = renderHook(() => useSearchRun(fast));
    act(() => result.current.selectFile(pngFile()));
    expect(result.current.selectedFileName).toBe("room.png");
    expect(result.current.previewUrl).toBeTruthy();
  });

  it("run without a file surfaces an error and stays empty", async () => {
    const { result } = renderHook(() => useSearchRun(fast));
    await act(async () => {
      await result.current.run();
    });
    expect(result.current.error).toMatch(/reference image/i);
    expect(result.current.scenario).toBe("empty");
  });

  it("run() completes and exposes surfaces + selected matches", async () => {
    const { result } = renderHook(() => useSearchRun(fast));
    act(() => result.current.selectFile(pngFile()));
    await act(async () => {
      await result.current.run();
    });
    await waitFor(() => expect(result.current.scenario).toBe("complete"));
    expect(createSearchRun).toHaveBeenCalledWith(
      expect.objectContaining({ prompt: "Find orderable materials in this image." }),
    );
    expect(result.current.surfaces.map((s) => s.region.label)).toEqual(["Floor", "Wall"]);
    expect(result.current.surfaces[0].matchCount).toBe(2);
    expect(result.current.selectedRegion?.label).toBe("Floor");
    expect(result.current.selectedMatches).toHaveLength(2);
    expect(result.current.selectedMatches[0].similarity).toBeCloseTo(0.96);
  });

  it("submits the entered prompt when provided", async () => {
    const { result } = renderHook(() => useSearchRun(fast));
    act(() => {
      result.current.selectFile(pngFile());
      result.current.setPrompt("  warm matte floor tile  ");
    });
    await act(async () => {
      await result.current.run();
    });
    expect(createSearchRun).toHaveBeenCalledWith(
      expect.objectContaining({ prompt: "warm matte floor tile" }),
    );
  });

  it("run() failure sets failed + error", async () => {
    vi.mocked(getSearchRunStatus).mockResolvedValue({
      ...completed,
      run: { ...completed.run, status: "failed", error: "segmenter timed out" },
      result: null,
    });
    const { result } = renderHook(() => useSearchRun(fast));
    act(() => result.current.selectFile(pngFile()));
    await act(async () => {
      await result.current.run();
    });
    await waitFor(() => expect(result.current.scenario).toBe("failed"));
    expect(result.current.error).toMatch(/timed out/i);
  });

  it("selectRegion switches the active matches", async () => {
    const { result } = renderHook(() => useSearchRun(fast));
    act(() => result.current.selectFile(pngFile()));
    await act(async () => {
      await result.current.run();
    });
    await waitFor(() => expect(result.current.scenario).toBe("complete"));
    act(() => result.current.selectRegion("r-wall"));
    expect(result.current.selectedRegion?.label).toBe("Wall");
    expect(result.current.selectedMatches).toHaveLength(1);
  });

  it("toggleCart adds/removes and computes cart items + surface count", async () => {
    const { result } = renderHook(() => useSearchRun(fast));
    act(() => result.current.selectFile(pngFile()));
    await act(async () => {
      await result.current.run();
    });
    await waitFor(() => expect(result.current.scenario).toBe("complete"));
    const floorMatchId = result.current.selectedMatches[0].id;
    act(() => result.current.toggleCart(floorMatchId));
    act(() => {
      result.current.selectRegion("r-wall");
    });
    const wallMatchId = result.current.selectedMatches[0].id;
    act(() => result.current.toggleCart(wallMatchId));
    expect(result.current.cartItems).toHaveLength(2);
    expect(result.current.cartSurfaceCount).toBe(2);
    act(() => result.current.toggleCart(floorMatchId));
    expect(result.current.cartItems).toHaveLength(1);
    expect(result.current.cartSurfaceCount).toBe(1);
  });
});
