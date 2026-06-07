import { Check, Circle, Loader2 } from "lucide-react";
import type { ProgressSnapshot, ProgressStage } from "../types";

type ProgressRevealProps = {
  snapshot: ProgressSnapshot;
};

type StepState = "pending" | "active" | "done";

const STAGE_ORDER: ProgressStage[] = ["planning", "segmenting", "matching", "complete"];

function reached(stage: ProgressStage, target: ProgressStage): boolean {
  return STAGE_ORDER.indexOf(stage) >= STAGE_ORDER.indexOf(target);
}

function StepIcon({ state }: { state: StepState }) {
  if (state === "done") return <Check size={15} aria-hidden="true" />;
  if (state === "active") return <Loader2 size={15} className="spin-icon" aria-hidden="true" />;
  return <Circle size={9} aria-hidden="true" />;
}

/**
 * Dedicated progress screen shown while a search run executes. Renders the
 * reference image as the hero with segment boxes lighting up, alongside a
 * narrated rail of pipeline stages (plan -> segment -> match) that each reveal
 * their artifact as it lands. Driven by a stream of ProgressSnapshots.
 */
export function ProgressReveal({ snapshot }: ProgressRevealProps) {
  const { stage, intent, plannedTargets, surfaces, previewUrl } = snapshot;

  const total = plannedTargets?.length ?? surfaces.length;
  const foundCount = surfaces.length;
  const matchedCount = surfaces.filter((s) => s.status === "matched").length;
  const scanning = stage === "planning" || stage === "segmenting";

  const understandingState: StepState = stage === "planning" ? "active" : "done";
  const findingState: StepState = !reached(stage, "segmenting")
    ? "pending"
    : stage === "segmenting"
      ? "active"
      : "done";
  const matchingState: StepState = !reached(stage, "matching")
    ? "pending"
    : stage === "matching"
      ? "active"
      : "done";
  const readyState: StepState = stage === "complete" ? "done" : "pending";

  const stageLabel =
    stage === "planning"
      ? "Understanding"
      : stage === "segmenting"
        ? "Finding surfaces"
        : stage === "matching"
          ? "Matching materials"
          : "Ready";

  return (
    <section className="progress wrap" aria-label="Search progress">
      <div className="progress-card">
        <div className={`progress-stage ${scanning ? "scanning" : ""}`}>
          {previewUrl ? (
            <img src={previewUrl} alt="Reference under analysis" />
          ) : (
            <div className="stage-empty swatch-fallback" />
          )}
          {scanning ? <span className="scan-line" aria-hidden="true" /> : null}
          {surfaces.map((surface) => (
            <div
              key={surface.id}
              className={`progress-box ${surface.status}`}
              style={{
                left: `${surface.box.left}%`,
                top: `${surface.box.top}%`,
                width: `${surface.box.width}%`,
                height: `${surface.box.height}%`,
              }}
            >
              {surface.status === "matching" ? (
                <span className="progress-box-scan" aria-hidden="true" />
              ) : null}
              <span className="progress-tag">
                {surface.label}
                {surface.status === "matched" ? (
                  <Check size={11} aria-hidden="true" />
                ) : surface.status === "matching" ? (
                  <span className="progress-tag-meta">· matching…</span>
                ) : surface.score != null ? (
                  <span className="progress-tag-meta">· {Math.round(surface.score * 100)}%</span>
                ) : null}
              </span>
            </div>
          ))}
        </div>

        <ol className="progress-rail" aria-live="polite">
          <li className="progress-eyebrow" aria-hidden="true">
            {stageLabel}
          </li>

          <li className={`progress-step ${understandingState}`}>
            <span className="progress-ic">
              <StepIcon state={understandingState} />
            </span>
            <div className="progress-step-body">
              <h3>Understanding your request</h3>
              <p className="progress-sub">
                {intent ?? "Reading your reference image and prompt…"}
              </p>
            </div>
          </li>

          <li className={`progress-step ${findingState}`}>
            <span className="progress-ic">
              <StepIcon state={findingState} />
            </span>
            <div className="progress-step-body">
              <h3>
                {findingState === "pending"
                  ? "Finding surfaces"
                  : findingState === "active"
                    ? `Finding surfaces — ${foundCount} of ${total}`
                    : `Found ${total} surface${total === 1 ? "" : "s"}`}
              </h3>
              {plannedTargets && plannedTargets.length > 0 ? (
                <div className="progress-chips">
                  {plannedTargets.map((label, index) => (
                    <span
                      key={label}
                      className={`progress-chip ${index < foundCount ? "found" : ""}`}
                    >
                      {label}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="progress-sub">Resolving floors, walls, textiles, stone…</p>
              )}
            </div>
          </li>

          <li className={`progress-step ${matchingState}`}>
            <span className="progress-ic">
              <StepIcon state={matchingState} />
            </span>
            <div className="progress-step-body">
              <h3>
                {matchingState === "done"
                  ? `Matched ${total} surface${total === 1 ? "" : "s"}`
                  : "Matching materials"}
              </h3>
              {matchingState !== "pending" ? (
                <>
                  <div
                    className="progress-bar"
                    role="progressbar"
                    aria-valuemin={0}
                    aria-valuemax={total}
                    aria-valuenow={matchedCount}
                  >
                    <i style={{ width: `${total ? (matchedCount / total) * 100 : 0}%` }} />
                  </div>
                  <div className="progress-thumbs">
                    {surfaces.map((surface) => (
                      <span
                        key={surface.id}
                        className={`progress-thumb ${surface.status === "matched" ? "" : "empty"}`}
                        style={
                          surface.status === "matched" && surface.thumbUrl
                            ? { backgroundImage: `url(${surface.thumbUrl})` }
                            : undefined
                        }
                      />
                    ))}
                  </div>
                  <p className="progress-sub">{matchedCount} of {total} surfaces</p>
                </>
              ) : (
                <p className="progress-sub">Searching the catalog for each surface.</p>
              )}
            </div>
          </li>

          <li className={`progress-step ${readyState}`}>
            <span className="progress-ic">
              <StepIcon state={readyState} />
            </span>
            <div className="progress-step-body">
              <h3>Ready</h3>
              <p className="progress-sub">
                {readyState === "done" ? "Opening your studio view." : "Building your studio view."}
              </p>
            </div>
          </li>
        </ol>
      </div>
    </section>
  );
}
