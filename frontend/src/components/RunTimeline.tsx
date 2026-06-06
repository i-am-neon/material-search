import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { RunStage } from "../types";

type RunTimelineProps = {
  stages: RunStage[];
  runLabel: string;
};

export function RunTimeline({ stages, runLabel }: RunTimelineProps) {
  return (
    <section className="run-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Run</p>
          <h2>Search status</h2>
        </div>
        <span className="run-id">{runLabel}</span>
      </div>

      <div className="stage-list">
        {stages.map((stage) => (
          <div className={`stage ${stage.status}`} key={stage.label}>
            <span className="stage-dot">
              {stage.status === "complete" ? <CheckCircle2 size={16} /> : null}
              {stage.status === "failed" ? <AlertTriangle size={15} /> : null}
            </span>
            <span>
              <strong>{stage.label}</strong>
              <small>{stage.detail}</small>
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
