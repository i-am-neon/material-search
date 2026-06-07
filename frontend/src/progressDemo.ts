import demoRoom from "./assets/demo-room.png";
import { matchesByRegion, regions as demoRegions } from "./demoData";
import type { ProgressSnapshot, ProgressStage, ProgressSurface } from "./types";

// Confidence scores for the demo surfaces (SAM3 would supply these at runtime).
const DEMO_SCORES: Record<string, number> = {
  "terrazzo-floor": 0.92,
  "walnut-panels": 0.88,
  "stone-counter": 0.74,
  "sage-fabric": 0.71,
};

const DEMO_INTENT =
  "Warm walnut paneling with cool aggregate flooring and soft sage textiles — hospitality-grade, quiet texture.";

// The full set of surfaces SAM3 will eventually resolve, in segmentation order.
const baseSurfaces = demoRegions.map((region) => {
  const topMatch = matchesByRegion[region.id]?.[0];
  return {
    id: region.id,
    label: region.label,
    box: region.box,
    score: DEMO_SCORES[region.id] ?? region.score ?? 0.8,
    matchCount: matchesByRegion[region.id]?.length ?? 0,
    thumbUrl: topMatch?.item.image_url ?? undefined,
  };
});

export const demoPlannedTargets = baseSurfaces.map((s) => s.label);

/**
 * Build one snapshot: `found` surfaces are segmented; `matched` of them are
 * fully matched; during the matching stage the next surface in line is shown
 * actively matching.
 */
function frame(stage: ProgressStage, found: number, matched: number): ProgressSnapshot {
  const surfaces: ProgressSurface[] = baseSurfaces.slice(0, found).map((surface, index) => {
    let status: ProgressSurface["status"] = "pending";
    if (index < matched) status = "matched";
    else if (stage === "matching" && index === matched) status = "matching";
    return { ...surface, status };
  });

  return {
    stage,
    previewUrl: demoRoom,
    intent: stage === "planning" ? undefined : DEMO_INTENT,
    plannedTargets: stage === "planning" ? undefined : demoPlannedTargets,
    surfaces,
  };
}

const total = baseSurfaces.length;

/**
 * The full reveal as the client would receive it: plan -> surfaces appear one
 * by one -> matches fill in surface by surface -> complete. Drives the
 * Storybook playthrough so we can iterate on the animation with no real calls.
 */
export const progressFrames: ProgressSnapshot[] = [
  frame("planning", 0, 0),
  frame("segmenting", 0, 0),
  ...baseSurfaces.map((_, i) => frame("segmenting", i + 1, 0)),
  ...baseSurfaces.map((_, i) => frame("matching", total, i)),
  frame("complete", total, total),
];

// Representative single frames for static stories.
export const planningFrame = frame("planning", 0, 0);
export const segmentingFrame = frame("segmenting", 2, 0);
export const matchingFrame = frame("matching", total, 2);
export const completeFrame = frame("complete", total, total);
