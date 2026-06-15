# Material Search — Studio UX Overhaul

**Date:** 2026-06-06
**Status:** Approved design, pending implementation plan
**Scope:** Frontend only (`frontend/src`). No backend or API changes.

## 1. Context & Goal

`material-search` lets a designer drop a reference image, runs SAM3 segmentation to detect
material surfaces, vector-matches each surface against an orderable catalog, and lets the user
collect samples. It is a portfolio piece aimed at the architecture & design (A&D) world, where
taste and brand matter. The visual bar is therefore as important as the AI.

**Problem with the current UI.** Once a search runs, intake, pipeline status, the region canvas,
and results all appear at once in a dense three-column `workspace-grid` (`SearchWorkbench.tsx:186`).
There is no hierarchy and no sense of progression. The styling leans on Inter and a forest-green
accent — generic, and not aligned with the near-monochrome, editorial brand the A&D world expects.

**Goal.** Re-architect the experience into two distinct phases with a deliberate seam between them,
and a refined grayscale, editorial design language where the *materials* are the only color.

## 2. The Core Insight (why this structure)

The reference image is the anchor of the entire experience. Every judgment the user makes — "is
this a good match?" — is made *relative to a surface in their image*. Therefore the image must stay
present during exploration, and exploration is **non-linear** (the user bounces between surfaces).
This rules out a full step-per-screen wizard for the results phase. The right cut is a single seam
between **setup** (linear, fast) and **exploration** (persistent, non-linear).

## 3. Experience Model: Two Phases

### Phase 1 — Intake (one focused screen)
A quiet, near-empty editorial screen. The dropzone and the intent prompt live together in **one
card** (upload and intent are one thought, not two steps). The AI pipeline is stated as a confident
footnote ("SAM 3 segmentation · Vector catalog match · 37k+ materials"), not a gimmick.

- Inputs: a reference image (drag-drop or browse; sample images still supported) + an optional intent prompt.
- Primary action: **"Read image."**
- Maps to current scenarios `empty`.

### Transition — Analysis as a moment, not a screen
On "Read image", the app uploads, creates a run, and polls (existing `handleRun` flow,
`SearchWorkbench.tsx:101`). Rather than a separate loading page, the **segmentation reveal animates
on the image itself** — the uploaded image comes forward and detected surfaces resolve onto it. This
is the SAM3 showpiece and is far more impressive on the real image than on a spinner.

- Maps to current scenarios `planning` (uploading / creating run) and `matching` (polling).
- If it fails (`failed`), show an inline error on the analysis surface with a retry, not a dead end.

### Phase 2 — Studio (one persistent workspace)
The reference image is **hero and permanent** on the left. Detected surfaces are outlined directly
on it; selecting a surface (on the image, or via the surface selector below it) drives the matches
gallery on the right. A sticky **Specification** tray collects picks across surfaces. The user
navigates *surfaces*, never screens; the image never leaves.

- Maps to current scenario `complete`.

## 4. Studio Layout — Components

```
┌── studio sub-header ──────────────────────────────────────────────┐
│  ← New search        [ Sourcing for "warm matte floor tile" ]   N surfaces · conf │
├───────────────────────────────┬───────────────────────────────────┤
│  REFERENCE (persistent)        │  MATCHES (for selected surface)   │
│  ┌─────────────────────────┐   │  Matching the floor   12 · ranked │
│  │  image w/ region overlays│   │  ┌────┐ ┌────┐ ┌────┐            │
│  │  [Floor*] [Wall] [Sofa]  │   │  │card│ │card│ │card│  …grid     │
│  └─────────────────────────┘   │  └────┘ └────┘ └────┘            │
│  surface pills: ● Floor 12 …   │                                   │
├───────────────────────────────┴───────────────────────────────────┤
│  SPECIFICATION  ▢▢▢  3 materials across 2 surfaces   [Order samples →] │  ← sticky tray
└────────────────────────────────────────────────────────────────────┘
```

### 4.1 Reference stage (persistent)
- The uploaded image, large, with absolutely-positioned region overlays driven by
  `MaterialRegion.box` (percentages already produced by `mapRunRegions`).
- Selected region: ink (black) outline + label chip. Unselected: white outline + muted label.
- Clicking a region overlay selects it (drives the matches column).

### 4.2 Surface selector
- A horizontal row of pills below the stage, one per detected surface, each showing a material-tone
  swatch, the surface label, and its match count.
- Active pill: solid ink. This and the on-image overlay are two views of the same selection state
  (`selectedRegionId`).

### 4.3 Matches gallery
- A roomy grid (3-up desktop, 2-up tablet, 1-up mobile) for the selected surface only.
- Each **match card**: material swatch/photo, similarity score badge, brand (uppercase label),
  product name (serif), a single "why it matched" line, sample price, and an add (+) control.
- Replaces the cramped `RegionInspector` right-rail list.

### 4.4 Specification tray (sticky)
- Sticky footer summarizing collected matches: overlapping swatch chips, "N materials across M
  surfaces", and a primary **"Order samples →"** action.
- Backed by existing `cartIds` state and `handleToggleCart`.

## 5. Design Language

### Typography
- **Display / headings:** `Fraunces` (variable, optical serif), upright only — no italic flourishes.
- **UI / body:** `Hanken Grotesk`.
- Remove Inter entirely.

### Color — grayscale chrome, materials are the only color
CSS custom properties (replace the current forest-green token set):

| Token | Value | Use |
|-------|-------|-----|
| `--paper` | `#F4F3F1` | page background |
| `--paper-2` | `#E8E7E4` | insets |
| `--card` | `#FFFFFF` | cards, surfaces |
| `--ink` | `#191919` | primary text, primary buttons, selected state |
| `--ink-2` | `#555452` | secondary text |
| `--ink-3` | `#8E8C88` | tertiary / labels |
| `--line` | `rgba(25,25,25,.14)` | borders |
| `--line-2` | `rgba(25,25,25,.07)` | hairlines |

No chromatic accent. Selected/active states use ink. Similarity badges are ink on translucent.
All color comes from material imagery (catalog photos in production; CSS textures in the mockup).

### Voice
Use the A&D sourcing vocabulary: **search → sample → specify**. Labels: "Sample · Free", "Order samples",
"Specification" — not generic e-commerce phrasing.

### Motion (restrained)
- Intake → studio: a single orchestrated reveal (surfaces resolving on the image), not scattered
  micro-interactions.
- Match cards: subtle lift on hover.

## 6. Component Architecture (clean rebuild of the view layer)

The frontend view layer is **not sacred — it is rebuilt from scratch** for this overhaul. Only the
genuinely valuable, well-tested logic is retained; everything in `components/` and `styles.css` is
fair game to replace.

**Retained (the data/logic layer):**
- `api.ts` — the upload / create-run / poll client, unchanged.
- `types.ts` — domain types (`MaterialRegion`, `ProductMatch`, etc.), adjusted only if a new view
  genuinely needs it.
- The run lifecycle logic currently in `SearchWorkbench.tsx` — the `scenario` state machine, the
  `handleRun` upload→create→poll flow, and the `mapRunRegions` / `mapRunMatches` adapters. This
  logic is sound; it will be **lifted into a hook** (e.g. `useSearchRun`) rather than left tangled
  in a component, so the new view components stay presentational.

**Rebuilt (the presentation layer):** new components, named for the new model:

| New component | Responsibility | Replaces |
|---------------|----------------|----------|
| `IntakeScreen` | Phase 1: dropzone + intent prompt in one card | `SearchSetup` (page) |
| `AnalysisReveal` | on-image segmentation reveal during `planning`/`matching`, inline error on `failed` | `RunTimeline` + rail `SearchSetup` |
| `StudioLayout` | the 2-column + sticky-tray shell for `complete` | `workspace-grid` |
| `ReferenceStage` | persistent hero image + region overlays + on-image selection | `RegionCanvas` |
| `SurfaceSelector` | surface pills bound to `selectedRegionId` | (new) |
| `MatchesGallery` / `MatchCard` | roomy match grid + redesigned card (§4.3) | `RegionInspector` + `ProductMatchCard` |
| `SpecificationTray` | sticky collected-samples footer | cart portion of `RegionInspector` |

`styles.css` is rewritten around the new tokens and components (old forest-green tokens removed).
A thin top-level component owns the phase switch (`empty`→Intake, `planning`/`matching`→Reveal,
`complete`→Studio) driven by the retained `useSearchRun` hook.

The `/catalog` route and `CatalogPage` are out of scope for the overhaul but should inherit the new
tokens for visual consistency (low-effort token swap only).

State-to-phase mapping (no new states needed):
- `empty` → IntakeScreen
- `planning` / `matching` → analysis reveal (on-image)
- `complete` → Studio
- `failed` → inline error on the analysis surface with retry

## 7. Data Flow & API
Unchanged. `uploadSearchImage` → `createSearchRun` → poll `getSearchRunStatus`
(`SearchWorkbench.tsx:114-136`). `mapRunRegions` / `mapRunMatches` continue to adapt the API
response into `MaterialRegion` / `ProductMatch`. No `types.ts` or `api.ts` changes required for the
core overhaul.

## 8. Responsive
- ≥1080px: two-column studio (reference | matches), 3-up match grid.
- 768–1080px: stacked — reference on top, matches below; 2-up match grid.
- <768px: single column; surface selector becomes a horizontal scroll; match grid 1-up; tray
  remains sticky.

## 9. Out of Scope (YAGNI)
- Backend, API, or data-model changes.
- The `/catalog` page redesign (token inheritance only).
- Real catalog photography sourcing for the mockup (production already returns `image_url`).
- Dark "gallery at night" variant (considered, deferred — light grayscale chosen).
- Multi-image / moodboard input, saved specifications, auth.

## 10. Success Criteria
- Two visually distinct phases with a clear seam; results phase keeps the image persistent.
- Zero chromatic accent in chrome; materials carry all color.
- Fraunces + Hanken Grotesk throughout; no Inter.
- Surface selection is reflected in both the on-image overlay and the selector pills.
- No regression in the existing run flow (upload → segment → match → cart).

## 11. Open Questions
- Should match cards support a quick side-by-side **compare** view, or is add-to-spec enough for v1?
  (Leaning: defer compare to a follow-up.)
- Does the analysis reveal need a minimum dwell time so it reads as a moment even when the run is
  fast? (Leaning: yes, a short floor, e.g. ~800ms.)
