import { AlertTriangle, RotateCcw } from "lucide-react";

type AnalysisRevealProps = {
  mode: "analyzing" | "failed";
  previewUrl?: string;
  imageWidth?: number;
  imageHeight?: number;
  error?: string | null;
  onRetry: () => void;
  onReset: () => void;
};

export function AnalysisReveal({ mode, previewUrl, imageWidth, imageHeight, error, onRetry, onReset }: AnalysisRevealProps) {
  const aspect = imageWidth && imageHeight ? { aspectRatio: `${imageWidth} / ${imageHeight}` } : undefined;

  return (
    <section className="analysis wrap" aria-label="Analyzing reference image">
      <div className={`analysis-stage ${mode === "analyzing" ? "scanning" : "failed"}`} style={aspect}>
        {previewUrl ? <img src={previewUrl} alt="Reference under analysis" /> : null}
        {mode === "analyzing" ? <span className="image-ripple" aria-hidden="true" /> : null}
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
              <h2>We couldn't read that one.</h2>
              <p>{error ?? "The segmenter didn't return any surfaces."}</p>
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
