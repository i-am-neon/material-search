import React from "react";
import ReactDOM from "react-dom/client";
import {
  CheckCircle2,
  ChevronDown,
  Clock3,
  Download,
  ImagePlus,
  Layers3,
  Play,
  Search,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import demoRoom from "./assets/demo-room.png";
import "./styles.css";

type RunStage = {
  label: string;
  status: "complete" | "active" | "queued";
};

type Region = {
  id: string;
  label: string;
  material: string;
  confidence: number;
  box: {
    left: number;
    top: number;
    width: number;
    height: number;
  };
  note: string;
};

type Match = {
  id: string;
  name: string;
  brand: string;
  type: string;
  score: number;
  family: string;
  finish: string;
  swatch: string;
};

const runStages: RunStage[] = [
  { label: "Plan concepts", status: "complete" },
  { label: "Segment regions", status: "complete" },
  { label: "Embed crops", status: "active" },
  { label: "Rank catalog", status: "queued" },
];

const regions: Region[] = [
  {
    id: "terrazzo-floor",
    label: "Terrazzo floor",
    material: "aggregate surface",
    confidence: 93,
    box: { left: 4, top: 67, width: 63, height: 25 },
    note: "Large, unobstructed region with visible aggregate and cool grey base.",
  },
  {
    id: "walnut-panels",
    label: "Walnut panels",
    material: "wood wall",
    confidence: 88,
    box: { left: 6, top: 20, width: 28, height: 40 },
    note: "Vertical grain reads consistently across panels, with moderate light variation.",
  },
  {
    id: "stone-counter",
    label: "Pale stone counter",
    material: "stone slab",
    confidence: 82,
    box: { left: 45, top: 45, width: 35, height: 16 },
    note: "Smooth light surface; crop includes enough edge detail for retrieval.",
  },
  {
    id: "sage-fabric",
    label: "Sage upholstery",
    material: "textile",
    confidence: 79,
    box: { left: 63, top: 55, width: 22, height: 28 },
    note: "Soft curved form; color is reliable, weave detail is partially visible.",
  },
];

const matches: Record<string, Match[]> = {
  "terrazzo-floor": [
    {
      id: "m-101",
      name: "Arco Micro Terrazzo",
      brand: "Northline Surfaces",
      type: "Tile",
      score: 94,
      family: "cool grey",
      finish: "honed",
      swatch:
        "radial-gradient(circle at 20% 25%, #f9f6ec 0 2px, transparent 3px), radial-gradient(circle at 70% 30%, #59646a 0 3px, transparent 4px), radial-gradient(circle at 52% 72%, #b48a68 0 2px, transparent 3px), #cfd2cc",
    },
    {
      id: "m-102",
      name: "Veneto Aggregate Ash",
      brand: "Materia Co.",
      type: "Slab",
      score: 91,
      family: "ash",
      finish: "matte",
      swatch:
        "radial-gradient(circle at 24% 30%, #6c777a 0 2px, transparent 3px), radial-gradient(circle at 68% 55%, #ece7dc 0 3px, transparent 4px), radial-gradient(circle at 42% 76%, #92897c 0 2px, transparent 3px), #b9bbb4",
    },
    {
      id: "m-103",
      name: "Palladio Mist Mix",
      brand: "Foundry Tile",
      type: "Porcelain",
      score: 87,
      family: "mist",
      finish: "satin",
      swatch:
        "radial-gradient(circle at 18% 62%, #d8d0be 0 3px, transparent 4px), radial-gradient(circle at 76% 22%, #566064 0 2px, transparent 3px), radial-gradient(circle at 62% 78%, #f5f0e4 0 2px, transparent 3px), #c9ccc6",
    },
  ],
  "walnut-panels": [
    {
      id: "m-201",
      name: "Linear Walnut Veneer",
      brand: "Canopy Woodworks",
      type: "Panel",
      score: 92,
      family: "walnut",
      finish: "clear matte",
      swatch:
        "repeating-linear-gradient(90deg, #6d452a 0 8px, #9b6840 8px 14px, #4c2e1d 14px 18px)",
    },
    {
      id: "m-202",
      name: "Warm Rift Timber",
      brand: "Studio Ply",
      type: "Veneer",
      score: 89,
      family: "brown",
      finish: "oiled",
      swatch:
        "repeating-linear-gradient(88deg, #7b4b2d 0 7px, #bb8151 7px 11px, #5b351f 11px 18px)",
    },
    {
      id: "m-203",
      name: "Acoustic Walnut Rib",
      brand: "Quietform",
      type: "Wall system",
      score: 85,
      family: "dark walnut",
      finish: "low sheen",
      swatch:
        "repeating-linear-gradient(90deg, #342115 0 6px, #8a5732 6px 10px, #24160f 10px 16px)",
    },
  ],
  "stone-counter": [
    {
      id: "m-301",
      name: "Calma Limestone",
      brand: "Atlas Stone",
      type: "Slab",
      score: 90,
      family: "warm white",
      finish: "honed",
      swatch:
        "linear-gradient(135deg, rgba(190, 176, 150, .4), transparent 38%), #e6e0d3",
    },
    {
      id: "m-302",
      name: "Soft Vein Porcelain",
      brand: "Linea Labs",
      type: "Porcelain",
      score: 86,
      family: "ivory",
      finish: "silk",
      swatch:
        "linear-gradient(112deg, transparent 0 40%, rgba(142, 130, 112, .42) 41% 43%, transparent 45%), #ece7dc",
    },
    {
      id: "m-303",
      name: "Dune Quartz Surface",
      brand: "Monolith",
      type: "Quartz",
      score: 83,
      family: "sandstone",
      finish: "matte",
      swatch:
        "linear-gradient(22deg, rgba(183, 153, 111, .25), transparent 48%), #ddd2bd",
    },
  ],
  "sage-fabric": [
    {
      id: "m-401",
      name: "Linden Contract Weave",
      brand: "Hearth Textiles",
      type: "Upholstery",
      score: 88,
      family: "sage",
      finish: "woven",
      swatch:
        "repeating-linear-gradient(45deg, rgba(255,255,255,.18) 0 2px, transparent 2px 5px), #849077",
    },
    {
      id: "m-402",
      name: "Olive Performance Linen",
      brand: "Trace Fabric",
      type: "Textile",
      score: 84,
      family: "green grey",
      finish: "linen",
      swatch:
        "repeating-linear-gradient(90deg, rgba(32,44,35,.16) 0 1px, transparent 1px 4px), #96a18e",
    },
    {
      id: "m-403",
      name: "Moss Felt Blend",
      brand: "Panel & Cloth",
      type: "Acoustic fabric",
      score: 80,
      family: "moss",
      finish: "felted",
      swatch:
        "radial-gradient(circle at 20% 20%, rgba(255,255,255,.15), transparent 18%), #6d7864",
    },
  ],
};

function App() {
  const [selectedRegionId, setSelectedRegionId] = React.useState(regions[0].id);
  const selectedRegion = regions.find((region) => region.id === selectedRegionId) ?? regions[0];
  const selectedMatches = matches[selectedRegion.id];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true">
          <Layers3 size={22} />
        </div>
        <div>
          <p className="eyebrow">Material Search</p>
          <h1>Visual catalog matching workbench</h1>
        </div>
        <div className="topbar-actions">
          <button className="icon-button" aria-label="Search history">
            <Clock3 size={18} />
          </button>
          <button className="icon-button" aria-label="Export run">
            <Download size={18} />
          </button>
        </div>
      </header>

      <section className="workspace-grid">
        <aside className="left-rail" aria-label="Search setup">
          <button className="upload-button">
            <ImagePlus size={18} />
            <span>Replace image</span>
          </button>

          <label className="field-label" htmlFor="request">
            Request
          </label>
          <textarea
            id="request"
            defaultValue="Find catalog materials matching the floor, wood paneling, counter surface, and upholstery."
          />

          <div className="filter-block">
            <div className="filter-title">
              <SlidersHorizontal size={16} />
              <span>Search controls</span>
            </div>
            <button className="select-row">
              <span>Catalog scope</span>
              <strong>Interior finishes</strong>
              <ChevronDown size={16} />
            </button>
            <button className="select-row">
              <span>Embedding model</span>
              <strong>SigLIP 2</strong>
              <ChevronDown size={16} />
            </button>
          </div>

          <button className="primary-action">
            <Play size={18} fill="currentColor" />
            <span>Run search</span>
          </button>
        </aside>

        <section className="image-panel" aria-label="Detected material regions">
          <div className="image-toolbar">
            <div>
              <p className="eyebrow">Uploaded Image</p>
              <h2>Hospitality lounge sample</h2>
            </div>
            <div className="status-pill">
              <Sparkles size={16} />
              <span>4 regions selected</span>
            </div>
          </div>

          <div className="image-canvas">
            <img src={demoRoom} alt="Contemporary lounge with multiple material surfaces" />
            {regions.map((region) => (
              <button
                key={region.id}
                className={`region-box ${region.id === selectedRegion.id ? "selected" : ""}`}
                style={{
                  left: `${region.box.left}%`,
                  top: `${region.box.top}%`,
                  width: `${region.box.width}%`,
                  height: `${region.box.height}%`,
                }}
                onClick={() => setSelectedRegionId(region.id)}
                aria-label={`Select ${region.label}`}
              >
                <span>{region.label}</span>
              </button>
            ))}
          </div>

          <div className="region-tabs" aria-label="Material regions">
            {regions.map((region) => (
              <button
                key={region.id}
                className={region.id === selectedRegion.id ? "active" : ""}
                onClick={() => setSelectedRegionId(region.id)}
              >
                <span>{region.label}</span>
                <strong>{region.confidence}%</strong>
              </button>
            ))}
          </div>
        </section>

        <aside className="right-rail" aria-label="Run status and matches">
          <section className="run-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Run</p>
                <h2>Search status</h2>
              </div>
              <span className="run-id">RUN-2406</span>
            </div>

            <div className="stage-list">
              {runStages.map((stage) => (
                <div className={`stage ${stage.status}`} key={stage.label}>
                  <span className="stage-dot">
                    {stage.status === "complete" ? <CheckCircle2 size={16} /> : null}
                  </span>
                  <span>{stage.label}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="selected-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Selected Region</p>
                <h2>{selectedRegion.label}</h2>
              </div>
              <span className="confidence">{selectedRegion.confidence}%</span>
            </div>
            <p>{selectedRegion.note}</p>
            <div className="metadata-grid">
              <span>Material</span>
              <strong>{selectedRegion.material}</strong>
              <span>Trust boundary</span>
              <strong>code-ranked</strong>
            </div>
          </section>

          <section className="matches-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Catalog</p>
                <h2>Top matches</h2>
              </div>
              <button className="small-action">
                <Search size={15} />
                <span>Refine</span>
              </button>
            </div>

            <div className="match-list">
              {selectedMatches.map((match) => (
                <article className="match-card" key={match.id}>
                  <div className="swatch" style={{ background: match.swatch }} />
                  <div>
                    <h3>{match.name}</h3>
                    <p>{match.brand}</p>
                    <div className="match-tags">
                      <span>{match.type}</span>
                      <span>{match.family}</span>
                      <span>{match.finish}</span>
                    </div>
                  </div>
                  <strong className="score">{match.score}</strong>
                </article>
              ))}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
