# Studio UX Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Material Search frontend into a two-phase experience — a quiet intake screen, an on-image analysis reveal, and a persistent "studio" workspace — with a grayscale, editorial design language where only the materials carry color.

**Architecture:** Keep the data layer (`api.ts`, `types.ts`) and lift the run-lifecycle logic out of `SearchWorkbench` into a tested `useSearchRun` hook. Rebuild the entire view layer as small, focused, presentational components driven by that hook. A thin `SearchWorkbench` switches between phases (`empty`→Intake, `planning`/`matching`→AnalysisReveal, `complete`→Studio, `failed`→AnalysisReveal error).

**Tech Stack:** React 18 + TypeScript + Vite, plain CSS (single `styles.css` with custom-property tokens), lucide-react icons, shadcn-style `ui/*` primitives, Storybook for visual stories. **New:** Vitest + React Testing Library + jsdom for unit/behavioral tests.

**Design source of truth:** the approved mockup at
`/Users/silver/dev/material-search/.superpowers/brainstorm/91822-1780771787/content/studio-grayscale-v2.html`
(gitignored, on disk). Open it in a browser while building — components port directly from it.

**Spec:** `docs/superpowers/specs/2026-06-06-material-search-studio-ux-design.md`

---

## Conventions for every task

- All paths are relative to `frontend/` unless noted. Run commands from `frontend/`.
- **Verification per task uses three gates:**
  1. `npm test -- --run` — unit/behavioral tests pass (after Task 1).
  2. `npm run build` — `tsc --noEmit && vite build` (typecheck + bundle) succeeds.
  3. A Storybook story is the visual artifact; spot-check with `npm run storybook` at component tasks and `npm run dev` at integration tasks.
- TDD: for components/hooks with behavior, write the failing test first. For purely presentational shells, the story is the artifact and the test asserts it renders key content.
- Commit after each task with the exact message given.

---

## File Structure

**Create**
- `vitest.setup.ts` — test setup (jest-dom matchers).
- `src/samples.ts` — `SampleImageOption` type, `sampleImages`, `fileFromSample()`.
- `src/hooks/useSearchRun.ts` — run state machine + selection + cart, lifted from `SearchWorkbench`.
- `src/hooks/useSearchRun.test.ts` — hook tests.
- `src/components/IntakeScreen.tsx` (+ `.test.tsx`, `.stories.tsx`)
- `src/components/AnalysisReveal.tsx` (+ `.test.tsx`, `.stories.tsx`)
- `src/components/studio/StudioScreen.tsx` (+ `.test.tsx`, `.stories.tsx`)
- `src/components/studio/ReferenceStage.tsx` (+ `.test.tsx`, `.stories.tsx`)
- `src/components/studio/SurfaceSelector.tsx` (+ `.test.tsx`, `.stories.tsx`)
- `src/components/studio/MatchesGallery.tsx` (+ `.stories.tsx`)
- `src/components/studio/MatchCard.tsx` (+ `.test.tsx`, `.stories.tsx`)
- `src/components/studio/SpecificationTray.tsx` (+ `.test.tsx`, `.stories.tsx`)

**Modify**
- `vite.config.ts` — add Vitest `test` config.
- `package.json` — add test deps + scripts.
- `index.html` — load Fraunces + Hanken Grotesk; update title.
- `src/styles.css` — rewrite around new tokens + components.
- `src/types.ts` — add `similarity?: number` to `ProductMatch`; remove `RunStage`/`RunStageStatus`.
- `src/demoData.ts` — add `similarity` to demo matches; remove `getRunStages`.
- `src/components/SearchWorkbench.tsx` — reduce to a thin phase-switching orchestrator.
- `src/components/SearchWorkbench.stories.tsx` — update to new render.

**Delete**
- `src/components/SearchSetup.tsx` + `SearchSetup.stories.tsx`
- `src/components/RegionCanvas.tsx`
- `src/components/RegionInspector.tsx` + `RegionInspector.stories.tsx`
- `src/components/ProductMatchCard.tsx` + `ProductMatchCard.stories.tsx`
- `src/components/RunTimeline.tsx` + `RunTimeline.stories.tsx`

---

## Task 1: Test harness (Vitest + RTL)

**Files:**
- Modify: `package.json`, `vite.config.ts`
- Create: `vitest.setup.ts`, `src/sanity.test.ts`

- [ ] **Step 1: Install test dependencies**

Run:
```bash
npm install -D vitest@^2.1.8 jsdom@^25.0.1 @testing-library/react@^16.1.0 @testing-library/jest-dom@^6.6.3 @testing-library/user-event@^14.5.2
```

- [ ] **Step 2: Add test scripts to `package.json`**

In the `"scripts"` block add:
```json
    "test": "vitest",
    "test:run": "vitest run"
```

- [ ] **Step 3: Configure Vitest in `vite.config.ts`**

Replace the file with:
```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/material-search/",
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    css: false,
  },
});
```

- [ ] **Step 4: Create `vitest.setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 5: Write a sanity test — `src/sanity.test.ts`**

```ts
import { describe, expect, it } from "vitest";

describe("test harness", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 6: Run it**

Run: `npm run test:run`
Expected: PASS, 1 test.

- [ ] **Step 7: Verify build still works**

Run: `npm run build`
Expected: succeeds (the `test` key on the Vite config is ignored by the build).

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json vite.config.ts vitest.setup.ts src/sanity.test.ts
git commit -m "test: add vitest + react-testing-library harness"
```

---

## Task 2: Design tokens, fonts, and CSS foundation

This task replaces the page-level look (background, type, topbar, intake) and establishes tokens.
Component-specific CSS is added in later tasks. Port values from the mockup file.

**Files:**
- Modify: `index.html`, `src/styles.css`

- [ ] **Step 1: Load fonts + fix title in `index.html`**

Inside `<head>`, after the `<link rel="icon" ...>`, add:
```html
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,500;9..144,600&family=Hanken+Grotesk:wght@400;500;600;700&display=swap"
      rel="stylesheet"
    />
```
Change the `<title>` to `Material / Search`.

- [ ] **Step 2: Replace the top of `src/styles.css` with the new foundation**

Replace everything from the start of the file down to (but not including) the first component-specific
rule that you will rebuild later. Practically: open `styles.css`, delete the entire file contents, and
paste the foundation below. Old component rules are intentionally dropped; later tasks re-add the rules
each new component needs.

```css
:root {
  --paper: #f4f3f1;
  --paper-2: #e8e7e4;
  --card: #ffffff;
  --ink: #191919;
  --ink-2: #555452;
  --ink-3: #8e8c88;
  --line: rgba(25, 25, 25, 0.14);
  --line-2: rgba(25, 25, 25, 0.07);
  --ink-deep: #000;
  --radius: 14px;

  color: var(--ink);
  background: var(--paper);
  font-family: "Hanken Grotesk", system-ui, sans-serif;
  font-synthesis: none;
  -webkit-font-smoothing: antialiased;
}

* { box-sizing: border-box; }
html, body, #root { margin: 0; min-height: 100%; }
body { background: var(--paper); color: var(--ink); line-height: 1.5; }

h1, h2, h3, h4 { font-family: "Fraunces", Georgia, serif; font-weight: 400; letter-spacing: -0.01em; margin: 0; }
.serif { font-family: "Fraunces", Georgia, serif; }
.eyebrow { font-size: 11px; letter-spacing: 0.24em; text-transform: uppercase; color: var(--ink-3); font-weight: 600; }

button { font-family: inherit; }

/* primitives used by ui/button.tsx (grayscale) */
.ui-button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; font-weight: 600; font-size: 13.5px; border-radius: 100px; border: 1px solid transparent; cursor: pointer; transition: background 0.18s, color 0.18s, border-color 0.18s; }
.ui-button:disabled { opacity: 0.45; cursor: not-allowed; }
.ui-button-size-default { padding: 11px 20px; }
.ui-button-size-sm { padding: 7px 14px; font-size: 12.5px; }
.ui-button-size-icon { padding: 9px; width: 38px; height: 38px; }
.ui-button-default { background: var(--ink); color: #fff; border-color: var(--ink); }
.ui-button-default:not(:disabled):hover { background: var(--ink-deep); }
.ui-button-secondary { background: var(--paper-2); color: var(--ink); }
.ui-button-outline { background: #fff; color: var(--ink); border-color: var(--line); }
.ui-button-outline:not(:disabled):hover { border-color: var(--ink-3); }
.ui-button-ghost { background: transparent; color: var(--ink-2); }
.ui-button-ghost:not(:disabled):hover { background: var(--paper-2); }

.ui-textarea { width: 100%; border: 1px solid var(--line); border-radius: 12px; background: #fff; padding: 12px 14px; font-family: inherit; font-size: 14px; color: var(--ink); resize: vertical; min-height: 92px; outline: none; }
.ui-textarea:focus { border-color: var(--ink-3); }

.spin-icon { animation: spin 0.9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* shell + topbar */
.app-shell { min-height: 100vh; display: flex; flex-direction: column; }
.topbar { display: flex; align-items: center; justify-content: space-between; padding: 22px 40px; border-bottom: 1px solid var(--line-2); }
.mark { display: flex; align-items: baseline; gap: 10px; }
.mark .logo { font-family: "Fraunces", serif; font-weight: 500; font-size: 20px; }
.mark .slash { color: var(--ink-3); }
.mark .sub { font-size: 11px; letter-spacing: 0.22em; text-transform: uppercase; color: var(--ink-3); }
.topnav { display: flex; gap: 26px; font-size: 13px; color: var(--ink-2); font-weight: 500; }
.topnav a { color: inherit; text-decoration: none; }
.topnav a.active { color: var(--ink); }

.wrap { max-width: 1240px; margin: 0 auto; padding: 0 40px; width: 100%; }

/* material swatch fallback when an item has no image */
.swatch-fallback { background: linear-gradient(135deg, #e3e0d8, #cfcabd); }

@media (max-width: 720px) {
  .topbar { padding: 16px 20px; }
  .wrap { padding: 0 20px; }
}
```

- [ ] **Step 3: Typecheck + build**

Run: `npm run build`
Expected: `tsc --noEmit` will FAIL because deleted CSS classes are still referenced by components not yet
replaced (e.g. `SearchSetup`). **This is expected mid-overhaul.** To keep this task self-verifying, only
assert the CSS itself is valid by running the bundler dev server briefly:

Run: `npx vite build --mode development 2>&1 | head -20`
Expected: no CSS parse errors reported for `styles.css`. (Type errors from stale components are addressed
as those components are replaced/deleted in later tasks.)

> Note: full green `npm run build` returns at Task 14 once obsolete components are deleted. Until then,
> rely on `npm run test:run` (green) and `npm run storybook` for per-task verification.

- [ ] **Step 4: Commit**

```bash
git add index.html src/styles.css
git commit -m "feat(ui): grayscale tokens, fonts, and shell foundation"
```

---

## Task 3: Domain type + samples module

**Files:**
- Modify: `src/types.ts`, `src/demoData.ts`
- Create: `src/samples.ts`

- [ ] **Step 1: Add `similarity` to `ProductMatch`, remove unused stage types — `src/types.ts`**

Add to `ProductMatch`:
```ts
export type ProductMatch = {
  id: string;
  fit: MatchFit;
  item: CatalogSeedItem;
  reasons: string[];
  similarity?: number; // 0..1 visual similarity when produced by a real run
};
```
Delete the `RunStageStatus` and `RunStage` type declarations entirely (they belong to the removed
`RunTimeline`).

- [ ] **Step 2: Remove `getRunStages` from `src/demoData.ts`**

Delete the entire `getRunStages` function and the `RunStage` import from the `./types` import list.
Leave `regions`, `matchesByRegion`, `defaultPrompt`, `catalogItems`, `materialFamilies`, `formatFamily`
intact (still used as demo fallback + by `CatalogPage`).

- [ ] **Step 3: Create `src/samples.ts`**

```ts
import demoRoom from "./assets/demo-room.png";

export type SampleImageOption = {
  id: string;
  name: string;
  src: string;
  filename: string;
};

export const sampleImages: SampleImageOption[] = [
  {
    id: "hospitality-lounge",
    name: "Hospitality lounge",
    src: demoRoom,
    filename: "hospitality-lounge-sample.png",
  },
];

export async function fileFromSample(sample: SampleImageOption): Promise<File> {
  const response = await fetch(sample.src);
  if (!response.ok) {
    throw new Error(`Could not load sample image ${sample.id}`);
  }
  const blob = await response.blob();
  return new File([blob], sample.filename, { type: blob.type || "image/png" });
}
```

- [ ] **Step 4: Typecheck the changed files**

Run: `npx tsc --noEmit 2>&1 | grep -E "types.ts|samples.ts|demoData.ts" || echo "no errors in changed files"`
Expected: `no errors in changed files` (errors elsewhere from stale components are fine for now).

- [ ] **Step 5: Commit**

```bash
git add src/types.ts src/demoData.ts src/samples.ts
git commit -m "feat: add match similarity field and samples module"
```

---

## Task 4: `useSearchRun` hook (TDD)

Lifts the run state machine, selection, and cart from `SearchWorkbench` into a tested hook with
injectable timing so tests run instantly.

**Files:**
- Create: `src/hooks/useSearchRun.ts`, `src/hooks/useSearchRun.test.ts`

- [ ] **Step 1: Write the failing tests — `src/hooks/useSearchRun.test.ts`**

```ts
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
      region: { id: "r-floor", prompt: "floor", score: 0.96, box_xyxy: [0, 600, 1000, 800] },
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
      region: { id: "r-wall", prompt: "wall", score: 0.82, box_xyxy: [0, 0, 600, 500] },
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
    expect(result.current.surfaces.map((s) => s.region.label)).toEqual(["Floor", "Wall"]);
    expect(result.current.surfaces[0].matchCount).toBe(2);
    expect(result.current.selectedRegion?.label).toBe("Floor");
    expect(result.current.selectedMatches).toHaveLength(2);
    expect(result.current.selectedMatches[0].similarity).toBeCloseTo(0.96);
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:run -- src/hooks/useSearchRun.test.ts`
Expected: FAIL — `useSearchRun` not found.

- [ ] **Step 3: Implement the hook — `src/hooks/useSearchRun.ts`**

```ts
import React from "react";
import {
  type SegmentMatchResponse,
  type SegmentRegionMatchSetResponse,
  createSearchRun,
  getSearchRunStatus,
  uploadSearchImage,
} from "../api";
import { defaultPrompt, matchesByRegion, regions as demoRegions } from "../demoData";
import { fileFromSample, type SampleImageOption } from "../samples";
import type { CatalogMetadata, MaterialRegion, ProductMatch, RunScenario } from "../types";

export type Surface = { region: MaterialRegion; matchCount: number; thumbUrl?: string };

export type UseSearchRunOptions = {
  initialScenario?: RunScenario;
  pollIntervalMs?: number;
  minAnalyzeMs?: number;
};

const DEFAULT_POLL_MS = 2000;
const DEFAULT_MIN_ANALYZE_MS = 800;
const POLL_ATTEMPTS = 90;

export function useSearchRun(options: UseSearchRunOptions = {}) {
  const {
    initialScenario = "empty",
    pollIntervalMs = DEFAULT_POLL_MS,
    minAnalyzeMs = DEFAULT_MIN_ANALYZE_MS,
  } = options;

  const [scenario, setScenario] = React.useState<RunScenario>(initialScenario);
  const [prompt, setPrompt] = React.useState(defaultPrompt);
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [selectedFileName, setSelectedFileName] = React.useState<string | undefined>();
  const [previewUrl, setPreviewUrl] = React.useState<string | undefined>();
  const [runResult, setRunResult] = React.useState<SegmentMatchResponse | null>(null);
  const [selectedRegionId, setSelectedRegionId] = React.useState(demoRegions[0].id);
  const [cartIds, setCartIds] = React.useState<string[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const previewObjectUrlRef = React.useRef<string | null>(null);
  const runSequenceRef = React.useRef(0);

  React.useEffect(() => {
    return () => {
      if (previewObjectUrlRef.current) URL.revokeObjectURL(previewObjectUrlRef.current);
    };
  }, []);

  const activeRegions: MaterialRegion[] = React.useMemo(
    () => (runResult ? mapRunRegions(runResult) : scenario === "complete" ? demoRegions : []),
    [runResult, scenario],
  );

  const matchesFor = React.useCallback(
    (regionId: string): ProductMatch[] => {
      if (runResult) return mapRunMatches(runResult, regionId);
      if (scenario === "complete") return matchesByRegion[regionId] ?? [];
      return [];
    },
    [runResult, scenario],
  );

  const surfaces: Surface[] = React.useMemo(
    () =>
      activeRegions.map((region) => {
        const matches = matchesFor(region.id);
        return { region, matchCount: matches.length, thumbUrl: matches[0]?.item.image_url ?? undefined };
      }),
    [activeRegions, matchesFor],
  );

  const selectedRegion =
    activeRegions.find((r) => r.id === selectedRegionId) ?? activeRegions[0];
  const selectedMatches = selectedRegion ? matchesFor(selectedRegion.id) : [];

  const cartItems = React.useMemo(
    () => activeRegions.flatMap((r) => matchesFor(r.id)).filter((m) => cartIds.includes(m.id)),
    [activeRegions, matchesFor, cartIds],
  );
  const cartSurfaceCount = React.useMemo(
    () => activeRegions.filter((r) => matchesFor(r.id).some((m) => cartIds.includes(m.id))).length,
    [activeRegions, matchesFor, cartIds],
  );

  const resetForNewImage = () => {
    setRunResult(null);
    setCartIds([]);
    setError(null);
    setScenario("empty");
    setSelectedRegionId(demoRegions[0].id);
  };

  const selectFile = (file: File) => {
    setSelectedFile(file);
    setSelectedFileName(file.name);
    resetForNewImage();
    if (previewObjectUrlRef.current) URL.revokeObjectURL(previewObjectUrlRef.current);
    previewObjectUrlRef.current = URL.createObjectURL(file);
    setPreviewUrl(previewObjectUrlRef.current);
  };

  const selectSample = async (sample: SampleImageOption) => {
    setError(null);
    try {
      const file = await fileFromSample(sample);
      setSelectedFile(file);
      setSelectedFileName(sample.name);
      resetForNewImage();
      if (previewObjectUrlRef.current) {
        URL.revokeObjectURL(previewObjectUrlRef.current);
        previewObjectUrlRef.current = null;
      }
      setPreviewUrl(sample.src);
    } catch {
      setError("Could not load the sample image. Try uploading your own image.");
    }
  };

  const run = async () => {
    if (!selectedFile) {
      setError("Choose a reference image before running search.");
      return;
    }
    setError(null);
    setRunResult(null);
    setCartIds([]);
    setScenario("planning");
    const seq = runSequenceRef.current + 1;
    runSequenceRef.current = seq;
    const startedAt = nowMs();
    try {
      const uploaded = await uploadSearchImage(selectedFile);
      const accepted = await createSearchRun({
        image_object_key: uploaded.image_object_key,
        prompt,
        confidence_threshold: 0.45,
        max_regions: 5,
        include_masks: false,
        matches_per_region: 6,
        min_similarity: 0,
      });
      if (seq !== runSequenceRef.current) return;
      setScenario("matching");
      const result = await pollSearchRun(accepted.run_id, pollIntervalMs);
      if (seq !== runSequenceRef.current) return;
      await ensureMinDuration(startedAt, minAnalyzeMs);
      if (seq !== runSequenceRef.current) return;
      setRunResult(result);
      setSelectedRegionId(result.regions[0]?.region.id ?? demoRegions[0].id);
      setScenario("complete");
    } catch (e) {
      if (seq !== runSequenceRef.current) return;
      setError(e instanceof Error ? e.message : "Search failed");
      setScenario("failed");
    }
  };

  const selectRegion = (id: string) => setSelectedRegionId(id);
  const toggleCart = (matchId: string) =>
    setCartIds((cur) => (cur.includes(matchId) ? cur.filter((x) => x !== matchId) : [...cur, matchId]));

  const isRunning = scenario === "planning" || scenario === "matching";

  return {
    scenario,
    prompt,
    setPrompt,
    selectedFileName,
    previewUrl,
    imageWidth: runResult?.image_width,
    imageHeight: runResult?.image_height,
    error,
    isRunning,
    selectFile,
    selectSample,
    run,
    surfaces,
    selectedRegionId: selectedRegion?.id ?? selectedRegionId,
    selectRegion,
    selectedRegion,
    selectedMatches,
    cartIds,
    toggleCart,
    cartItems,
    cartSurfaceCount,
  };
}

function nowMs(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}

async function ensureMinDuration(startedAt: number, minMs: number): Promise<void> {
  const elapsed = nowMs() - startedAt;
  if (elapsed < minMs) await delay(minMs - elapsed);
}

async function pollSearchRun(runId: string, intervalMs: number): Promise<SegmentMatchResponse> {
  for (let attempt = 0; attempt < POLL_ATTEMPTS; attempt += 1) {
    const status = await getSearchRunStatus(runId);
    if (status.run.status === "completed") {
      if (!status.result) throw new Error("Search completed without persisted results.");
      return status.result;
    }
    if (status.run.status === "failed") throw new Error(status.run.error ?? "Search failed");
    await delay(intervalMs);
  }
  throw new Error("Search is still running. Try refreshing the run status.");
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function mapRunRegions(result: SegmentMatchResponse): MaterialRegion[] {
  return result.regions.map(({ region }, index) => {
    const [x0, y0, x1, y1] = region.box_xyxy;
    return {
      id: region.id,
      label: result.regions[index].target_label ?? `Region ${index + 1}`,
      material: result.regions[index].target_label ?? region.prompt,
      confidence: confidenceLabel(region.score),
      box: {
        left: percent(x0, result.image_width),
        top: percent(y0, result.image_height),
        width: percent(x1 - x0, result.image_width),
        height: percent(y1 - y0, result.image_height),
      },
      note: `SAM3 identified this area with ${Math.round(region.score * 100)}% confidence.`,
      searchIntent: result.plan?.user_intent_summary ?? result.prompt,
      included: true,
      score: region.score,
    };
  });
}

function mapRunMatches(result: SegmentMatchResponse, regionId: string): ProductMatch[] {
  const matchSet = result.regions.find((c) => c.region.id === regionId);
  if (!matchSet) return [];
  return matchSet.matches.map((m) => ({
    id: `${regionId}-${m.match.item.id}`,
    fit: fitLabel(m.rank),
    item: {
      id: m.match.item.id,
      manufacturer: m.match.item.manufacturer,
      name: m.match.item.name,
      material_family: m.match.item.material_family,
      image_object_key: m.match.item.image_object_key,
      image_url: m.match.item.image_url,
      metadata: normalizeMetadata(m.match.item.metadata),
    },
    reasons: matchReasons(matchSet),
    similarity: m.match.similarity,
  }));
}

function matchReasons(matchSet: SegmentRegionMatchSetResponse): string[] {
  const lead = matchSet.region.prompt
    ? `Matches the ${matchSet.region.prompt} surface`
    : "Close visual + material match";
  return [lead, "Orderable catalog item"];
}

function normalizeMetadata(metadata: Record<string, unknown>): CatalogMetadata {
  return {
    colorway: stringValue(metadata.colorway),
    collection: stringValue(metadata.collection),
    image_kind: stringValue(metadata.image_kind),
    materials: stringArrayValue(metadata.materials),
    source_platform: stringValue(metadata.source_platform),
    source_url: stringValue(metadata.source_url),
    visual_tags: stringArrayValue(metadata.visual_tags),
  };
}

const stringValue = (v: unknown) => (typeof v === "string" ? v : undefined);
const stringArrayValue = (v: unknown) =>
  Array.isArray(v) && v.every((i) => typeof i === "string") ? (v as string[]) : undefined;

function percent(value: number, total: number): number {
  if (!total) return 0;
  return Math.max(0, Math.min(100, (value / total) * 100));
}

function confidenceLabel(score: number): MaterialRegion["confidence"] {
  if (score >= 0.8) return "High";
  if (score >= 0.55) return "Medium";
  return "Needs review";
}

function fitLabel(rank: number): ProductMatch["fit"] {
  if (rank === 1) return "Best fit";
  if (rank <= 3) return "Close alternate";
  return "Creative option";
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:run -- src/hooks/useSearchRun.test.ts`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useSearchRun.ts src/hooks/useSearchRun.test.ts
git commit -m "feat: useSearchRun hook with tests (lift run state machine)"
```

---

## Task 5: IntakeScreen (Phase 1)

Port the intake half of the mockup: an editorial copy column + a single card combining the dropzone and
the intent prompt.

**Files:**
- Create: `src/components/IntakeScreen.tsx`, `src/components/IntakeScreen.test.tsx`, `src/components/IntakeScreen.stories.tsx`
- Modify: `src/styles.css` (append intake rules)

- [ ] **Step 1: Write the failing test — `src/components/IntakeScreen.test.tsx`**

```tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/components/IntakeScreen.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/components/IntakeScreen.tsx`**

```tsx
import React from "react";
import { ArrowRight, ImagePlus, Loader2, Upload } from "lucide-react";
import { sampleImages, type SampleImageOption } from "../samples";

type IntakeScreenProps = {
  prompt: string;
  selectedFileName?: string;
  previewUrl?: string;
  isRunning: boolean;
  error?: string | null;
  onPromptChange: (value: string) => void;
  onPickFile: (file: File) => void;
  onPickSample: (sample: SampleImageOption) => void;
  onRun: () => void;
};

export function IntakeScreen({
  prompt,
  selectedFileName,
  previewUrl,
  isRunning,
  error,
  onPromptChange,
  onPickFile,
  onPickSample,
  onRun,
}: IntakeScreenProps) {
  const fileInputId = React.useId();
  const canRun = Boolean(selectedFileName) && !isRunning;

  return (
    <section className="intake-body wrap" aria-label="New material search">
      <div className="intake-copy">
        <p className="eyebrow">Visual material sourcing</p>
        <h1 className="intake-headline">
          Source it
          <br />
          from an <span>image</span>.
        </h1>
        <p className="intake-lede">
          Drop in a room, a surface, an inspiration. We read every material in it — and match it to
          what you can actually sample.
        </p>
        <div className="pipeline-note">
          <span><b>SAM&nbsp;3</b> segmentation</span>
          <span className="dot">·</span>
          <span><b>Vector</b> catalog match</span>
          <span className="dot">·</span>
          <span><b>37k+</b> materials</span>
        </div>
      </div>

      <div className="intake-card">
        <label className="dz-canvas" htmlFor={fileInputId}>
          {previewUrl ? (
            <img className="dz-preview" src={previewUrl} alt={selectedFileName ?? "Reference"} />
          ) : (
            <>
              <span className="dz-icon"><ImagePlus size={22} /></span>
              <span className="dz-title">Drop a reference image</span>
              <span className="dz-sub">or browse — JPG, PNG, WebP</span>
            </>
          )}
          <input
            id={fileInputId}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => {
              const file = e.currentTarget.files?.[0];
              if (file) onPickFile(file);
              e.currentTarget.value = "";
            }}
          />
        </label>

        {sampleImages.length ? (
          <button
            type="button"
            className="dz-sample"
            onClick={() => onPickSample(sampleImages[0])}
          >
            <Upload size={14} />
            <span>or start with the {sampleImages[0].name.toLowerCase()} sample</span>
          </button>
        ) : null}

        <div className="dz-prompt">
          <input
            value={prompt}
            placeholder="What are you sourcing?  e.g. a warm matte floor tile"
            onChange={(e) => onPromptChange(e.currentTarget.value)}
          />
          <button type="button" className="ui-button ui-button-default ui-button-size-default" disabled={!canRun} onClick={onRun}>
            {isRunning ? <Loader2 className="spin-icon" size={15} /> : null}
            <span>Read image</span>
            {!isRunning ? <ArrowRight size={15} /> : null}
          </button>
        </div>

        {error ? <p className="form-error">{error}</p> : null}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Append intake CSS to `src/styles.css`**

```css
/* ---- Phase 1: Intake ---- */
.intake-body { flex: 1; display: grid; grid-template-columns: 1.05fr 0.95fr; align-items: center; gap: 60px; padding-top: 40px; padding-bottom: 40px; }
.intake-copy .eyebrow { margin-bottom: 22px; }
.intake-headline { font-weight: 300; font-size: clamp(40px, 5.4vw, 74px); line-height: 1.02; margin-bottom: 24px; }
.intake-headline span { font-weight: 300; }
.intake-lede { font-size: 17px; color: var(--ink-2); max-width: 30ch; margin: 0 0 30px; }
.pipeline-note { display: flex; gap: 14px; font-size: 12px; color: var(--ink-3); }
.pipeline-note b { color: var(--ink-2); font-weight: 600; }

.intake-card { background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 14px; box-shadow: 0 30px 60px -34px rgba(0, 0, 0, 0.4); }
.dz-canvas { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; text-align: center; border: 1.5px dashed rgba(25, 25, 25, 0.32); border-radius: 12px; aspect-ratio: 5 / 4; cursor: pointer; overflow: hidden; background: repeating-linear-gradient(45deg, rgba(25, 25, 25, 0.018) 0 12px, transparent 12px 24px); }
.dz-canvas input[type="file"] { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.dz-preview { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.dz-icon { width: 46px; height: 46px; border-radius: 12px; background: var(--paper-2); display: flex; align-items: center; justify-content: center; color: var(--ink); }
.dz-title { font-family: "Fraunces", serif; font-size: 21px; }
.dz-sub { font-size: 13px; color: var(--ink-3); }
.dz-sample { display: inline-flex; align-items: center; gap: 7px; margin: 12px auto 0; background: none; border: 0; color: var(--ink-2); font-size: 12.5px; cursor: pointer; }
.dz-sample:hover { color: var(--ink); }
.dz-prompt { display: flex; align-items: center; gap: 10px; margin-top: 14px; padding: 6px 6px 6px 18px; border: 1px solid var(--line); border-radius: 100px; background: var(--paper); }
.dz-prompt input { flex: 1; border: 0; background: transparent; font-family: inherit; font-size: 14px; color: var(--ink); outline: none; }
.dz-prompt input::placeholder { color: var(--ink-3); }
.form-error { color: #9a3434; font-size: 13px; margin: 12px 4px 0; }

@media (max-width: 880px) { .intake-body { grid-template-columns: 1fr; gap: 32px; } }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test:run -- src/components/IntakeScreen.test.tsx`
Expected: PASS, 3 tests.

- [ ] **Step 6: Write the story — `src/components/IntakeScreen.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { IntakeScreen } from "./IntakeScreen";

const meta: Meta<typeof IntakeScreen> = {
  title: "Studio/IntakeScreen",
  component: IntakeScreen,
  parameters: { layout: "fullscreen" },
  args: {
    prompt: "a warm matte floor tile",
    isRunning: false,
    error: null,
    onPromptChange: () => {},
    onPickFile: () => {},
    onPickSample: () => {},
    onRun: () => {},
  },
};
export default meta;
type Story = StoryObj<typeof IntakeScreen>;

export const Empty: Story = {};
export const WithFile: Story = { args: { selectedFileName: "room.png" } };
export const Running: Story = { args: { selectedFileName: "room.png", isRunning: true } };
export const WithError: Story = { args: { error: "Choose a reference image before running search." } };
```

- [ ] **Step 7: Spot-check in Storybook (manual)**

Run: `npm run storybook` and open `Studio/IntakeScreen`. Confirm the layout matches the intake half of
the mockup. Stop Storybook when done.

- [ ] **Step 8: Commit**

```bash
git add src/components/IntakeScreen.tsx src/components/IntakeScreen.test.tsx src/components/IntakeScreen.stories.tsx src/styles.css
git commit -m "feat(ui): IntakeScreen with dropzone + intent prompt"
```

---

## Task 6: AnalysisReveal (transition)

Shows the uploaded image with an animated scan sweep during `planning`/`matching`, and an inline error +
retry during `failed`. Ported from the mockup's `.m-scan` motion idea.

**Files:**
- Create: `src/components/AnalysisReveal.tsx`, `src/components/AnalysisReveal.test.tsx`, `src/components/AnalysisReveal.stories.tsx`
- Modify: `src/styles.css`

- [ ] **Step 1: Write the failing test — `src/components/AnalysisReveal.test.tsx`**

```tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/components/AnalysisReveal.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/components/AnalysisReveal.tsx`**

```tsx
import { AlertTriangle, RotateCcw } from "lucide-react";

type AnalysisRevealProps = {
  mode: "analyzing" | "failed";
  previewUrl?: string;
  error?: string | null;
  onRetry: () => void;
  onReset: () => void;
};

export function AnalysisReveal({ mode, previewUrl, error, onRetry, onReset }: AnalysisRevealProps) {
  return (
    <section className="analysis wrap" aria-label="Analyzing reference image">
      <div className={`analysis-stage ${mode === "analyzing" ? "scanning" : "failed"}`}>
        {previewUrl ? <img src={previewUrl} alt="Reference under analysis" /> : null}
        {mode === "analyzing" ? <span className="scan-line" aria-hidden="true" /> : null}
        <div className="analysis-caption">
          {mode === "analyzing" ? (
            <>
              <span className="analysis-eyebrow">SAM 3</span>
              <h2>Reading the image…</h2>
              <p>Resolving material surfaces — floors, walls, textiles, stone.</p>
            </>
          ) : (
            <>
              <span className="analysis-eyebrow error"><AlertTriangle size={14} /> Analysis failed</span>
              <h2>We couldn’t read that one.</h2>
              <p>{error ?? "The segmenter didn’t return any surfaces."}</p>
              <div className="analysis-actions">
                <button type="button" className="ui-button ui-button-default ui-button-size-default" onClick={onRetry}>
                  <RotateCcw size={15} /> Try again
                </button>
                <button type="button" className="ui-button ui-button-ghost ui-button-size-default" onClick={onReset}>
                  New image
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Append analysis CSS to `src/styles.css`**

```css
/* ---- Transition: Analysis reveal ---- */
.analysis { flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px; }
.analysis-stage { position: relative; width: min(760px, 100%); border-radius: 18px; overflow: hidden; border: 1px solid var(--line); box-shadow: 0 30px 60px -34px rgba(0, 0, 0, 0.5); background: var(--paper-2); aspect-ratio: 3 / 2; }
.analysis-stage img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.analysis-stage.scanning img { filter: grayscale(0.2) contrast(1.02); }
.scan-line { position: absolute; top: 0; bottom: 0; width: 36%; background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.85), transparent); mix-blend-mode: overlay; animation: scan-sweep 1.8s ease-in-out infinite; }
@keyframes scan-sweep { 0% { transform: translateX(-60%); } 100% { transform: translateX(280%); } }
.analysis-caption { position: absolute; left: 0; right: 0; bottom: 0; padding: 22px 26px; background: linear-gradient(0deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0)); }
.analysis-eyebrow { font-size: 11px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--ink-3); font-weight: 700; display: inline-flex; align-items: center; gap: 6px; }
.analysis-eyebrow.error { color: #9a3434; }
.analysis-caption h2 { font-size: 24px; margin: 6px 0 4px; }
.analysis-caption p { font-size: 14px; color: var(--ink-2); margin: 0; }
.analysis-actions { display: flex; gap: 10px; margin-top: 14px; }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test:run -- src/components/AnalysisReveal.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 6: Write the story — `src/components/AnalysisReveal.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { AnalysisReveal } from "./AnalysisReveal";
import demoRoom from "../assets/demo-room.png";

const meta: Meta<typeof AnalysisReveal> = {
  title: "Studio/AnalysisReveal",
  component: AnalysisReveal,
  parameters: { layout: "fullscreen" },
  args: { previewUrl: demoRoom, onRetry: () => {}, onReset: () => {} },
};
export default meta;
type Story = StoryObj<typeof AnalysisReveal>;

export const Analyzing: Story = { args: { mode: "analyzing", error: null } };
export const Failed: Story = { args: { mode: "failed", error: "Segmenter timed out" } };
```

- [ ] **Step 7: Commit**

```bash
git add src/components/AnalysisReveal.tsx src/components/AnalysisReveal.test.tsx src/components/AnalysisReveal.stories.tsx src/styles.css
git commit -m "feat(ui): on-image AnalysisReveal transition"
```

---

## Task 7: ReferenceStage (persistent image + regions)

**Files:**
- Create: `src/components/studio/ReferenceStage.tsx`, `.test.tsx`, `.stories.tsx`
- Modify: `src/styles.css`

- [ ] **Step 1: Write the failing test — `src/components/studio/ReferenceStage.test.tsx`**

```tsx
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
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/components/studio/ReferenceStage.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/components/studio/ReferenceStage.tsx`**

```tsx
import type { MaterialRegion } from "../../types";

type ReferenceStageProps = {
  previewUrl?: string;
  regions: MaterialRegion[];
  selectedRegionId: string;
  imageWidth?: number;
  imageHeight?: number;
  onSelect: (regionId: string) => void;
};

export function ReferenceStage({
  previewUrl,
  regions,
  selectedRegionId,
  imageWidth,
  imageHeight,
  onSelect,
}: ReferenceStageProps) {
  const aspect = imageWidth && imageHeight ? { aspectRatio: `${imageWidth} / ${imageHeight}` } : undefined;
  return (
    <div className="ref-col">
      <div className="ref-head">
        <h2>Your reference</h2>
        <span className="ref-meta">tap a surface</span>
      </div>
      <div className="stage" style={aspect}>
        {previewUrl ? <img src={previewUrl} alt="Reference" /> : <div className="stage-empty swatch-fallback" />}
        {regions
          .filter((r) => r.included)
          .map((region) => (
            <button
              key={region.id}
              type="button"
              className={`region ${region.id === selectedRegionId ? "sel" : ""}`}
              style={{
                left: `${region.box.left}%`,
                top: `${region.box.top}%`,
                width: `${region.box.width}%`,
                height: `${region.box.height}%`,
              }}
              onClick={() => onSelect(region.id)}
              aria-label={`Select ${region.label}`}
            >
              <span className="tag">{region.id === selectedRegionId ? `${region.label} · selected` : region.label}</span>
            </button>
          ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Append reference-stage CSS to `src/styles.css`**

```css
/* ---- Studio: reference stage ---- */
.ref-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 14px; }
.ref-head h2 { font-size: 24px; }
.ref-meta { font-size: 12px; color: var(--ink-3); }
.stage { position: relative; border-radius: 16px; overflow: hidden; border: 1px solid var(--line); box-shadow: 0 24px 48px -30px rgba(0, 0, 0, 0.5); aspect-ratio: 5 / 4; background: var(--paper-2); }
.stage img { display: block; width: 100%; height: 100%; object-fit: cover; }
.stage-empty { position: absolute; inset: 0; }
.region { position: absolute; border: 2px solid rgba(255, 255, 255, 0.9); border-radius: 8px; cursor: pointer; box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.3), 0 8px 22px rgba(0, 0, 0, 0.22); background: transparent; }
.region .tag { position: absolute; top: -12px; left: 8px; font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 700; background: rgba(255, 255, 255, 0.94); color: var(--ink-2); padding: 3px 8px; border-radius: 6px; white-space: nowrap; }
.region.sel { border-color: #fff; box-shadow: 0 0 0 2px var(--ink), 0 14px 30px rgba(0, 0, 0, 0.4); background: rgba(25, 25, 25, 0.14); }
.region.sel .tag { background: var(--ink); color: #fff; }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test:run -- src/components/studio/ReferenceStage.test.tsx`
Expected: PASS.

- [ ] **Step 6: Story — `src/components/studio/ReferenceStage.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { ReferenceStage } from "./ReferenceStage";
import { regions } from "../../demoData";
import demoRoom from "../../assets/demo-room.png";

const meta: Meta<typeof ReferenceStage> = {
  title: "Studio/ReferenceStage",
  component: ReferenceStage,
  args: { previewUrl: demoRoom, regions, selectedRegionId: regions[0].id, onSelect: () => {} },
  decorators: [(S) => <div style={{ maxWidth: 520, padding: 24 }}><S /></div>],
};
export default meta;
type Story = StoryObj<typeof ReferenceStage>;
export const Default: Story = {};
```

- [ ] **Step 7: Commit**

```bash
git add src/components/studio/ReferenceStage.tsx src/components/studio/ReferenceStage.test.tsx src/components/studio/ReferenceStage.stories.tsx src/styles.css
git commit -m "feat(ui): persistent ReferenceStage with on-image regions"
```

---

## Task 8: SurfaceSelector

**Files:**
- Create: `src/components/studio/SurfaceSelector.tsx`, `.test.tsx`, `.stories.tsx`
- Modify: `src/styles.css`

- [ ] **Step 1: Write the failing test — `src/components/studio/SurfaceSelector.test.tsx`**

```tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/components/studio/SurfaceSelector.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `src/components/studio/SurfaceSelector.tsx`**

```tsx
import type { Surface } from "../../hooks/useSearchRun";

type SurfaceSelectorProps = {
  surfaces: Surface[];
  selectedRegionId: string;
  onSelect: (regionId: string) => void;
};

export function SurfaceSelector({ surfaces, selectedRegionId, onSelect }: SurfaceSelectorProps) {
  return (
    <div className="surfaces" role="tablist" aria-label="Detected surfaces">
      {surfaces.map(({ region, matchCount, thumbUrl }) => (
        <button
          key={region.id}
          type="button"
          role="tab"
          aria-selected={region.id === selectedRegionId}
          className={`surf ${region.id === selectedRegionId ? "active" : ""}`}
          onClick={() => onSelect(region.id)}
        >
          <span className={`surf-sw ${thumbUrl ? "" : "swatch-fallback"}`} style={thumbUrl ? { backgroundImage: `url(${thumbUrl})` } : undefined} />
          <span className="surf-label">{region.label}</span>
          <span className="surf-count">{matchCount}</span>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Append surface-selector CSS to `src/styles.css`**

```css
/* ---- Studio: surface selector ---- */
.surfaces { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
.surf { display: flex; align-items: center; gap: 9px; border: 1px solid var(--line); background: var(--card); border-radius: 100px; padding: 7px 14px 7px 8px; font-size: 13px; color: var(--ink-2); cursor: pointer; transition: 0.15s; }
.surf-sw { width: 18px; height: 18px; border-radius: 5px; background-size: cover; background-position: center; }
.surf-label { font-weight: 500; }
.surf-count { font-size: 11px; color: var(--ink-3); }
.surf.active { border-color: var(--ink); color: #fff; background: var(--ink); box-shadow: 0 6px 16px -6px rgba(0, 0, 0, 0.5); }
.surf.active .surf-count { color: rgba(255, 255, 255, 0.6); }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test:run -- src/components/studio/SurfaceSelector.test.tsx`
Expected: PASS.

- [ ] **Step 6: Story — `src/components/studio/SurfaceSelector.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { SurfaceSelector } from "./SurfaceSelector";
import { regions, matchesByRegion } from "../../demoData";
import type { Surface } from "../../hooks/useSearchRun";

const surfaces: Surface[] = regions.map((region) => ({
  region,
  matchCount: matchesByRegion[region.id]?.length ?? 0,
  thumbUrl: matchesByRegion[region.id]?.[0]?.item.image_url ?? undefined,
}));

const meta: Meta<typeof SurfaceSelector> = {
  title: "Studio/SurfaceSelector",
  component: SurfaceSelector,
  args: { surfaces, selectedRegionId: regions[0].id, onSelect: () => {} },
};
export default meta;
type Story = StoryObj<typeof SurfaceSelector>;
export const Default: Story = {};
```

- [ ] **Step 7: Commit**

```bash
git add src/components/studio/SurfaceSelector.tsx src/components/studio/SurfaceSelector.test.tsx src/components/studio/SurfaceSelector.stories.tsx src/styles.css
git commit -m "feat(ui): SurfaceSelector pills"
```

---

## Task 9: MatchCard

**Files:**
- Create: `src/components/studio/MatchCard.tsx`, `.test.tsx`, `.stories.tsx`
- Modify: `src/styles.css`

- [ ] **Step 1: Write the failing test — `src/components/studio/MatchCard.test.tsx`**

```tsx
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
  it("renders brand, name, similarity and toggles cart", async () => {
    const onToggleCart = vi.fn();
    render(<MatchCard match={match} inCart={false} onToggleCart={onToggleCart} />);
    expect(screen.getByText("Listone Giordano")).toBeInTheDocument();
    expect(screen.getByText("Heritage Oak")).toBeInTheDocument();
    expect(screen.getByText("96%")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /add to specification/i }));
    expect(onToggleCart).toHaveBeenCalledWith("floor-oak");
  });

  it("shows in-spec state", () => {
    render(<MatchCard match={match} inCart onToggleCart={vi.fn()} />);
    expect(screen.getByRole("button", { name: /in specification/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/components/studio/MatchCard.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `src/components/studio/MatchCard.tsx`**

```tsx
import { Check, Plus } from "lucide-react";
import { formatFamily } from "../../demoData";
import type { ProductMatch } from "../../types";

type MatchCardProps = {
  match: ProductMatch;
  inCart: boolean;
  onToggleCart: (matchId: string) => void;
};

export function MatchCard({ match, inCart, onToggleCart }: MatchCardProps) {
  const { item } = match;
  const family = formatFamily(item.material_family ?? "uncategorized");
  const why = match.reasons[0];
  const label = inCart ? "In specification" : "Add to specification";

  return (
    <article className="mcard">
      <div className={`mswatch ${item.image_url ? "" : "swatch-fallback"}`}>
        {item.image_url ? <img src={item.image_url} alt={`${item.manufacturer} ${item.name}`} /> : null}
        {typeof match.similarity === "number" ? (
          <span className="sim">{Math.round(match.similarity * 100)}%</span>
        ) : null}
      </div>
      <div className="mbody">
        <div className="brand">{item.manufacturer}</div>
        <h4>{item.name}</h4>
        {why ? <p className="why">{why}</p> : null}
        <div className="madd">
          <span className="sample-note">Sample · {family}</span>
          <button
            type="button"
            className={`plus ${inCart ? "added" : ""}`}
            aria-label={label}
            title={label}
            onClick={() => onToggleCart(match.id)}
          >
            {inCart ? <Check size={16} /> : <Plus size={16} />}
          </button>
        </div>
      </div>
    </article>
  );
}
```

- [ ] **Step 4: Append match-card CSS to `src/styles.css`**

```css
/* ---- Studio: match card ---- */
.mcard { background: var(--card); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; transition: 0.18s; }
.mcard:hover { transform: translateY(-4px); box-shadow: 0 22px 40px -24px rgba(0, 0, 0, 0.5); border-color: var(--ink-3); }
.mswatch { position: relative; aspect-ratio: 1; }
.mswatch img { width: 100%; height: 100%; object-fit: cover; }
.sim { position: absolute; top: 9px; right: 9px; background: rgba(25, 25, 25, 0.82); color: #fff; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 100px; }
.mbody { padding: 12px 13px 14px; }
.mbody .brand { font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-3); font-weight: 600; }
.mbody h4 { font-size: 16px; margin: 3px 0 7px; }
.why { font-size: 12px; color: var(--ink-2); line-height: 1.45; margin: 0; display: flex; gap: 6px; }
.why::before { content: ""; width: 3px; border-radius: 2px; background: var(--ink); flex: none; }
.madd { margin-top: 11px; display: flex; align-items: center; justify-content: space-between; }
.sample-note { font-size: 12px; color: var(--ink-3); text-transform: capitalize; }
.plus { width: 30px; height: 30px; border-radius: 100px; border: 1px solid var(--line); background: #fff; color: var(--ink); display: flex; align-items: center; justify-content: center; cursor: pointer; transition: 0.15s; }
.plus:hover, .plus.added { background: var(--ink); color: #fff; border-color: var(--ink); }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test:run -- src/components/studio/MatchCard.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 6: Story — `src/components/studio/MatchCard.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { MatchCard } from "./MatchCard";
import { matchesByRegion } from "../../demoData";

const sample = { ...matchesByRegion["terrazzo-floor"][0], similarity: 0.96 };

const meta: Meta<typeof MatchCard> = {
  title: "Studio/MatchCard",
  component: MatchCard,
  args: { match: sample, inCart: false, onToggleCart: () => {} },
  decorators: [(S) => <div style={{ width: 240, padding: 24 }}><S /></div>],
};
export default meta;
type Story = StoryObj<typeof MatchCard>;
export const Default: Story = {};
export const InSpecification: Story = { args: { inCart: true } };
```

- [ ] **Step 7: Commit**

```bash
git add src/components/studio/MatchCard.tsx src/components/studio/MatchCard.test.tsx src/components/studio/MatchCard.stories.tsx src/styles.css
git commit -m "feat(ui): redesigned MatchCard"
```

---

## Task 10: MatchesGallery

**Files:**
- Create: `src/components/studio/MatchesGallery.tsx`, `.stories.tsx`
- Modify: `src/styles.css`

- [ ] **Step 1: Implement `src/components/studio/MatchesGallery.tsx`**

(Presentational grid; verified via story + the StudioScreen integration test in Task 12.)

```tsx
import { MatchCard } from "./MatchCard";
import type { ProductMatch } from "../../types";

type MatchesGalleryProps = {
  surfaceLabel?: string;
  matches: ProductMatch[];
  cartIds: string[];
  onToggleCart: (matchId: string) => void;
};

export function MatchesGallery({ surfaceLabel, matches, cartIds, onToggleCart }: MatchesGalleryProps) {
  return (
    <div className="match-col">
      <div className="matches-head">
        <h2>Matching the <span>{surfaceLabel ?? "surface"}</span></h2>
        <span className="matches-ct">{matches.length} materials · ranked by similarity</span>
      </div>
      {matches.length ? (
        <div className="match-grid">
          {matches.map((match) => (
            <MatchCard key={match.id} match={match} inCart={cartIds.includes(match.id)} onToggleCart={onToggleCart} />
          ))}
        </div>
      ) : (
        <p className="muted-copy">No catalog matches for this surface yet.</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Append gallery CSS to `src/styles.css`**

```css
/* ---- Studio: matches gallery ---- */
.matches-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 18px; gap: 16px; }
.matches-head h2 { font-size: 24px; }
.matches-head h2 span { font-style: normal; }
.matches-ct { font-size: 12px; color: var(--ink-3); white-space: nowrap; }
.match-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.muted-copy { color: var(--ink-3); font-size: 14px; }
@media (max-width: 1080px) { .match-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 560px) { .match-grid { grid-template-columns: 1fr; } }
```

- [ ] **Step 3: Story — `src/components/studio/MatchesGallery.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { MatchesGallery } from "./MatchesGallery";
import { matchesByRegion } from "../../demoData";

const meta: Meta<typeof MatchesGallery> = {
  title: "Studio/MatchesGallery",
  component: MatchesGallery,
  parameters: { layout: "fullscreen" },
  args: {
    surfaceLabel: "floor",
    matches: matchesByRegion["terrazzo-floor"].map((m, i) => ({ ...m, similarity: 0.96 - i * 0.05 })),
    cartIds: [],
    onToggleCart: () => {},
  },
  decorators: [(S) => <div style={{ padding: 32 }}><S /></div>],
};
export default meta;
type Story = StoryObj<typeof MatchesGallery>;
export const Default: Story = {};
```

- [ ] **Step 4: Verify it typechecks + tests still green**

Run: `npm run test:run`
Expected: all prior tests PASS (no test added here; gallery is covered in Task 12).

- [ ] **Step 5: Commit**

```bash
git add src/components/studio/MatchesGallery.tsx src/components/studio/MatchesGallery.stories.tsx src/styles.css
git commit -m "feat(ui): MatchesGallery grid"
```

---

## Task 11: SpecificationTray

**Files:**
- Create: `src/components/studio/SpecificationTray.tsx`, `.test.tsx`, `.stories.tsx`
- Modify: `src/styles.css`

- [ ] **Step 1: Write the failing test — `src/components/studio/SpecificationTray.test.tsx`**

```tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/components/studio/SpecificationTray.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `src/components/studio/SpecificationTray.tsx`**

```tsx
import { ArrowRight } from "lucide-react";
import type { ProductMatch } from "../../types";

type SpecificationTrayProps = {
  items: ProductMatch[];
  surfaceCount: number;
  onOrder: () => void;
};

export function SpecificationTray({ items, surfaceCount, onOrder }: SpecificationTrayProps) {
  const surfaceWord = surfaceCount === 1 ? "surface" : "surfaces";
  const materialWord = items.length === 1 ? "material" : "materials";
  return (
    <div className="tray">
      <div className="tray-in wrap">
        <div className="tray-left">
          <span className="tray-lbl">Specification</span>
          <div className="tray-sw">
            {items.slice(0, 5).map((m) => (
              <span
                key={m.id}
                className={`tray-chip ${m.item.image_url ? "" : "swatch-fallback"}`}
                style={m.item.image_url ? { backgroundImage: `url(${m.item.image_url})` } : undefined}
              />
            ))}
          </div>
          <span className="tray-count">
            <b>{items.length}</b> {materialWord} across {surfaceCount} {surfaceWord}
          </span>
        </div>
        <button type="button" className="ui-button ui-button-default ui-button-size-default" disabled={!items.length} onClick={onOrder}>
          <span>Order samples</span>
          <ArrowRight size={15} />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Append tray CSS to `src/styles.css`**

```css
/* ---- Studio: specification tray ---- */
.tray { position: sticky; bottom: 0; margin-top: 34px; background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(10px); border-top: 1px solid var(--line); }
.tray-in { display: flex; align-items: center; justify-content: space-between; padding: 14px 40px; }
.tray-left { display: flex; align-items: center; gap: 18px; }
.tray-lbl { font-size: 11px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--ink-3); font-weight: 600; }
.tray-sw { display: flex; }
.tray-chip { width: 34px; height: 34px; border-radius: 8px; border: 2px solid var(--card); margin-left: -8px; background-size: cover; background-position: center; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2); }
.tray-chip:first-child { margin-left: 0; }
.tray-count { font-size: 13px; color: var(--ink-2); }
.tray-count b { font-family: "Fraunces", serif; font-weight: 500; color: var(--ink); font-size: 15px; }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test:run -- src/components/studio/SpecificationTray.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 6: Story — `src/components/studio/SpecificationTray.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { SpecificationTray } from "./SpecificationTray";
import { matchesByRegion } from "../../demoData";

const meta: Meta<typeof SpecificationTray> = {
  title: "Studio/SpecificationTray",
  component: SpecificationTray,
  parameters: { layout: "fullscreen" },
  args: {
    items: [matchesByRegion["terrazzo-floor"][0], matchesByRegion["walnut-panels"][0], matchesByRegion["sage-fabric"][0]],
    surfaceCount: 3,
    onOrder: () => {},
  },
};
export default meta;
type Story = StoryObj<typeof SpecificationTray>;
export const Default: Story = {};
export const Empty: Story = { args: { items: [], surfaceCount: 0 } };
```

- [ ] **Step 7: Commit**

```bash
git add src/components/studio/SpecificationTray.tsx src/components/studio/SpecificationTray.test.tsx src/components/studio/SpecificationTray.stories.tsx src/styles.css
git commit -m "feat(ui): sticky SpecificationTray"
```

---

## Task 12: StudioScreen (compose Phase 2)

**Files:**
- Create: `src/components/studio/StudioScreen.tsx`, `.test.tsx`, `.stories.tsx`
- Modify: `src/styles.css`

- [ ] **Step 1: Write the failing test — `src/components/studio/StudioScreen.test.tsx`**

```tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/components/studio/StudioScreen.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement `src/components/studio/StudioScreen.tsx`**

```tsx
import { ArrowLeft } from "lucide-react";
import type { MaterialRegion, ProductMatch } from "../../types";
import type { Surface } from "../../hooks/useSearchRun";
import { ReferenceStage } from "./ReferenceStage";
import { SurfaceSelector } from "./SurfaceSelector";
import { MatchesGallery } from "./MatchesGallery";
import { SpecificationTray } from "./SpecificationTray";

type StudioScreenProps = {
  prompt: string;
  previewUrl?: string;
  imageWidth?: number;
  imageHeight?: number;
  surfaces: Surface[];
  selectedRegion?: MaterialRegion;
  selectedRegionId: string;
  selectedMatches: ProductMatch[];
  cartIds: string[];
  cartItems: ProductMatch[];
  cartSurfaceCount: number;
  onSelectRegion: (regionId: string) => void;
  onToggleCart: (matchId: string) => void;
  onNewSearch: () => void;
  onOrder: () => void;
};

export function StudioScreen({
  prompt,
  previewUrl,
  imageWidth,
  imageHeight,
  surfaces,
  selectedRegion,
  selectedRegionId,
  selectedMatches,
  cartIds,
  cartItems,
  cartSurfaceCount,
  onSelectRegion,
  onToggleCart,
  onNewSearch,
  onOrder,
}: StudioScreenProps) {
  const avgConfidence = surfaces.length
    ? surfaces.reduce((sum, s) => sum + (s.region.score ?? 0), 0) / surfaces.length
    : 0;

  return (
    <section className="studio" aria-label="Material studio">
      <div className="studio-sub">
        <div className="studio-intent">
          <button type="button" className="studio-back" onClick={onNewSearch}>
            <ArrowLeft size={14} /> New search
          </button>
          <span className="chip">Sourcing for <span className="chip-q">“{prompt}”</span></span>
        </div>
        <div className="studio-meta">
          {surfaces.length} surfaces detected{avgConfidence ? ` · ${avgConfidence.toFixed(2)} avg confidence` : ""}
        </div>
      </div>

      <div className="studio-grid wrap">
        <ReferenceStage
          previewUrl={previewUrl}
          regions={surfaces.map((s) => s.region)}
          selectedRegionId={selectedRegionId}
          imageWidth={imageWidth}
          imageHeight={imageHeight}
          onSelect={onSelectRegion}
        />
        <div className="studio-right">
          <MatchesGallery
            surfaceLabel={selectedRegion?.label}
            matches={selectedMatches}
            cartIds={cartIds}
            onToggleCart={onToggleCart}
          />
        </div>
      </div>
      <div className="studio-grid wrap studio-selector-row">
        <SurfaceSelector surfaces={surfaces} selectedRegionId={selectedRegionId} onSelect={onSelectRegion} />
        <div />
      </div>

      <SpecificationTray items={cartItems} surfaceCount={cartSurfaceCount} onOrder={onOrder} />
    </section>
  );
}
```

> Note: the surface selector renders in its own row under the reference column for layout simplicity;
> CSS hides the empty right cell. This keeps `ReferenceStage` focused on the image only.

- [ ] **Step 4: Append studio-shell CSS to `src/styles.css`**

```css
/* ---- Studio: shell ---- */
.studio { display: flex; flex-direction: column; flex: 1; }
.studio-sub { display: flex; align-items: center; justify-content: space-between; padding: 18px 40px; border-bottom: 1px solid var(--line-2); flex-wrap: wrap; gap: 10px; }
.studio-intent { display: flex; align-items: center; gap: 12px; }
.studio-back { display: inline-flex; align-items: center; gap: 6px; background: none; border: 0; font-size: 12.5px; color: var(--ink-2); cursor: pointer; }
.studio-back:hover { color: var(--ink); }
.chip { display: inline-flex; align-items: center; gap: 8px; background: var(--card); border: 1px solid var(--line); border-radius: 100px; padding: 6px 14px; font-size: 12.5px; color: var(--ink); }
.chip-q { font-weight: 600; }
.studio-meta { font-size: 12.5px; color: var(--ink-2); }
.studio-grid { display: grid; grid-template-columns: minmax(420px, 1fr) 1.25fr; gap: 34px; padding-top: 34px; align-items: start; }
.studio-selector-row { padding-top: 0; margin-top: 16px; }
.studio-selector-row .surfaces { margin-top: 0; }
@media (max-width: 1080px) {
  .studio-grid { grid-template-columns: 1fr; }
  .studio-selector-row > div:last-child { display: none; }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm run test:run -- src/components/studio/StudioScreen.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 6: Story — `src/components/studio/StudioScreen.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { StudioScreen } from "./StudioScreen";
import { regions, matchesByRegion } from "../../demoData";
import type { Surface } from "../../hooks/useSearchRun";
import demoRoom from "../../assets/demo-room.png";

const surfaces: Surface[] = regions.map((region) => ({
  region,
  matchCount: matchesByRegion[region.id]?.length ?? 0,
  thumbUrl: matchesByRegion[region.id]?.[0]?.item.image_url ?? undefined,
}));

const meta: Meta<typeof StudioScreen> = {
  title: "Studio/StudioScreen",
  component: StudioScreen,
  parameters: { layout: "fullscreen" },
  args: {
    prompt: "a warm matte floor tile",
    previewUrl: demoRoom,
    surfaces,
    selectedRegion: regions[0],
    selectedRegionId: regions[0].id,
    selectedMatches: matchesByRegion[regions[0].id].map((m, i) => ({ ...m, similarity: 0.96 - i * 0.05 })),
    cartIds: [],
    cartItems: [],
    cartSurfaceCount: 0,
    onSelectRegion: () => {},
    onToggleCart: () => {},
    onNewSearch: () => {},
    onOrder: () => {},
  },
};
export default meta;
type Story = StoryObj<typeof StudioScreen>;
export const Default: Story = {};
```

- [ ] **Step 7: Commit**

```bash
git add src/components/studio/StudioScreen.tsx src/components/studio/StudioScreen.test.tsx src/components/studio/StudioScreen.stories.tsx src/styles.css
git commit -m "feat(ui): StudioScreen composing the persistent workspace"
```

---

## Task 13: Rewrite SearchWorkbench orchestrator

Wire the hook + the three phases. Keep the `SearchWorkbench` name so `App.tsx` routing is unchanged.

**Files:**
- Modify: `src/components/SearchWorkbench.tsx`, `src/components/SearchWorkbench.stories.tsx`
- Create: `src/components/SearchWorkbench.test.tsx`

- [ ] **Step 1: Write the failing integration test — `src/components/SearchWorkbench.test.tsx`**

```tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/components/SearchWorkbench.test.tsx`
Expected: FAIL (current `SearchWorkbench` has a different shape / imports deleted components after Task 14; right now it still compiles but won't match these assertions). If it errors on imports, that's also a failing state — proceed to implement.

- [ ] **Step 3: Rewrite `src/components/SearchWorkbench.tsx`**

```tsx
import { Grid2X2, Layers3, ShoppingCart } from "lucide-react";
import { Link } from "react-router-dom";
import { useSearchRun, type UseSearchRunOptions } from "../hooks/useSearchRun";
import type { RunScenario } from "../types";
import { IntakeScreen } from "./IntakeScreen";
import { AnalysisReveal } from "./AnalysisReveal";
import { StudioScreen } from "./studio/StudioScreen";

type SearchWorkbenchProps = {
  initialScenario?: RunScenario;
  testTiming?: Pick<UseSearchRunOptions, "pollIntervalMs" | "minAnalyzeMs">;
};

export function SearchWorkbench({ initialScenario = "empty", testTiming }: SearchWorkbenchProps) {
  const run = useSearchRun({ initialScenario, ...testTiming });

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="mark">
          <span className="brand-glyph" aria-hidden="true"><Layers3 size={20} /></span>
          <span className="logo">Material<span className="slash"> / </span>Search</span>
          <span className="sub">A&amp;D Sourcing</span>
        </div>
        <nav className="topnav">
          <Link className="active" to="/">Search</Link>
          <Link to="/catalog"><Grid2X2 size={15} /> Catalog</Link>
          <span className="topnav-cart"><ShoppingCart size={15} /> {run.cartIds.length}</span>
        </nav>
      </header>

      {run.scenario === "empty" ? (
        <IntakeScreen
          prompt={run.prompt}
          selectedFileName={run.selectedFileName}
          previewUrl={run.previewUrl}
          isRunning={run.isRunning}
          error={run.error}
          onPromptChange={run.setPrompt}
          onPickFile={run.selectFile}
          onPickSample={run.selectSample}
          onRun={run.run}
        />
      ) : null}

      {run.scenario === "planning" || run.scenario === "matching" ? (
        <AnalysisReveal mode="analyzing" previewUrl={run.previewUrl} error={null} onRetry={run.run} onReset={() => window.location.reload()} />
      ) : null}

      {run.scenario === "failed" ? (
        <AnalysisReveal mode="failed" previewUrl={run.previewUrl} error={run.error} onRetry={run.run} onReset={() => window.location.reload()} />
      ) : null}

      {run.scenario === "complete" ? (
        <StudioScreen
          prompt={run.prompt}
          previewUrl={run.previewUrl}
          imageWidth={run.imageWidth}
          imageHeight={run.imageHeight}
          surfaces={run.surfaces}
          selectedRegion={run.selectedRegion}
          selectedRegionId={run.selectedRegionId}
          selectedMatches={run.selectedMatches}
          cartIds={run.cartIds}
          cartItems={run.cartItems}
          cartSurfaceCount={run.cartSurfaceCount}
          onSelectRegion={run.selectRegion}
          onToggleCart={run.toggleCart}
          onNewSearch={() => window.location.reload()}
          onOrder={() => {}}
        />
      ) : null}
    </main>
  );
}
```

> `onNewSearch`/`onReset` use a full reload for v1 simplicity (the hook owns all state). A future
> iteration can expose a `reset()` from the hook; out of scope here.

- [ ] **Step 4: Append topbar-cart CSS to `src/styles.css`**

```css
.brand-glyph { display: inline-flex; color: var(--ink); }
.topnav a { display: inline-flex; align-items: center; gap: 6px; }
.topnav-cart { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-2); }
```

- [ ] **Step 5: Update `src/components/SearchWorkbench.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react";
import { MemoryRouter } from "react-router-dom";
import { SearchWorkbench } from "./SearchWorkbench";

const meta: Meta<typeof SearchWorkbench> = {
  title: "Studio/SearchWorkbench",
  component: SearchWorkbench,
  parameters: { layout: "fullscreen" },
  decorators: [(S) => <MemoryRouter><S /></MemoryRouter>],
};
export default meta;
type Story = StoryObj<typeof SearchWorkbench>;

export const Intake: Story = { args: { initialScenario: "empty" } };
export const Studio: Story = { args: { initialScenario: "complete" } };
```

- [ ] **Step 6: Run test to verify it passes**

Run: `npm run test:run -- src/components/SearchWorkbench.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 7: Commit**

```bash
git add src/components/SearchWorkbench.tsx src/components/SearchWorkbench.stories.tsx src/components/SearchWorkbench.test.tsx src/styles.css
git commit -m "feat(ui): thin SearchWorkbench orchestrator over useSearchRun"
```

---

## Task 14: Delete obsolete components + full green build

**Files:**
- Delete: `SearchSetup.tsx`, `SearchSetup.stories.tsx`, `RegionCanvas.tsx`, `RegionInspector.tsx`, `RegionInspector.stories.tsx`, `ProductMatchCard.tsx`, `ProductMatchCard.stories.tsx`, `RunTimeline.tsx`, `RunTimeline.stories.tsx`

- [ ] **Step 1: Delete the obsolete files**

```bash
cd src/components
git rm SearchSetup.tsx SearchSetup.stories.tsx RegionCanvas.tsx RegionInspector.tsx RegionInspector.stories.tsx ProductMatchCard.tsx ProductMatchCard.stories.tsx RunTimeline.tsx RunTimeline.stories.tsx
cd ../..
```

- [ ] **Step 2: Search for dangling references**

Run: `grep -rEn "SearchSetup|RegionCanvas|RegionInspector|ProductMatchCard|RunTimeline|getRunStages|RunStage" src || echo "clean"`
Expected: `clean`. If anything prints, remove/replace those references (they should only be in files
already rewritten).

- [ ] **Step 3: Full typecheck + build (now expected to pass)**

Run: `npm run build`
Expected: `tsc --noEmit` passes and `vite build` produces a bundle with no errors.

- [ ] **Step 4: Full test run**

Run: `npm run test:run`
Expected: ALL tests PASS.

- [ ] **Step 5: Manual visual pass against the mockup**

Run: `npm run dev` and open the printed URL.
- Intake screen matches the mockup's intake half (Fraunces headline, single card, grayscale).
- Choose the sample image → click **Read image** → the analysis reveal scans on the image → the studio
  appears with the image persistent, surfaces selectable, matches in a roomy grid, sticky tray.
- Switch surfaces; add items; confirm the tray count + surface count update.
Stop the dev server when satisfied.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(ui): remove legacy workbench components"
```

---

## Task 15: Catalog token inheritance + final verification

`CatalogPage` is out of scope for redesign but must not look broken under the new tokens.

**Files:**
- Modify: `src/styles.css` (only if `CatalogPage` rules reference removed tokens/classes)
- Review: `src/components/CatalogPage.tsx`

- [ ] **Step 1: Inspect CatalogPage for stale classes**

Run: `grep -oE "className=\"[^\"]+\"" src/components/CatalogPage.tsx | sort -u`
For any class it uses that no longer exists in `styles.css`, add a minimal grayscale rule (background
`var(--card)`, border `var(--line)`, text `var(--ink)`) so the page reads as part of the new system.
Do not redesign it.

- [ ] **Step 2: Visually confirm `/catalog`**

Run: `npm run dev`, open `/#/catalog`. Confirm it renders legibly in grayscale (no forest-green
leftovers, no unstyled blocks). Stop the server.

- [ ] **Step 3: Final gates**

Run: `npm run test:run && npm run build`
Expected: both green.

- [ ] **Step 4: Commit**

```bash
git add src/styles.css src/components/CatalogPage.tsx
git commit -m "style: catalog page inherits grayscale tokens"
```

---

## Self-Review (completed during authoring)

**Spec coverage:**
- Two-phase model → Tasks 5/6/12/13. ✓
- Image-anchored persistent studio → Task 7 + 12. ✓
- Surface navigation (overlay + pills share state) → Tasks 7, 8, 12 via `selectedRegionId`. ✓
- Roomy matches + redesigned card → Tasks 9, 10. ✓
- Specification tray (cart) → Task 11; cart logic in hook Task 4. ✓
- Grayscale tokens, Fraunces + Hanken Grotesk, no Inter → Tasks 1(fonts in 2)/2. ✓
- Voice (search → sample → specify) → "Specification", "Order samples", "Add to specification". ✓
- Analysis-as-a-moment + min dwell (spec §11) → `AnalysisReveal` (Task 6) + `minAnalyzeMs` in hook (Task 4). ✓
- Retain api.ts/types/run-logic; lift into hook → Task 4. ✓
- /catalog token inheritance → Task 15. ✓
- Defer compare view (spec §11) → not built; honored. ✓

**Type consistency:** `Surface` defined in `useSearchRun.ts` and imported by `SurfaceSelector`,
`StudioScreen`, and stories. `ProductMatch.similarity?` added in Task 3 and produced in Task 4's
`mapRunMatches`, consumed in Task 9 `MatchCard`. Hook return field names
(`selectedRegionId`, `selectedMatches`, `cartItems`, `cartSurfaceCount`, `surfaces`) match
`SearchWorkbench` (Task 13) and `StudioScreen` (Task 12) usage.

**Placeholder scan:** none — every step contains concrete code or an exact command.

**Known intentional deviation:** strict unit-TDD is applied to the hook and interactive components;
purely presentational shells (`MatchesGallery`) are covered by their consumer's integration test
(`StudioScreen`) plus a story, rather than a standalone test. Mid-overhaul, full `npm run build` is red
between Tasks 2–13 (stale components reference removed CSS); `npm run test:run` stays green throughout
and full build returns green at Task 14.
