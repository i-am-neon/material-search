import catalogSeed from "../../data/catalog/material-bank-style-seed.json";
import type { CatalogSeedItem, MaterialRegion, ProductMatch, RunScenario, RunStage } from "./types";

export const catalogItems = catalogSeed.items as CatalogSeedItem[];

export const materialFamilies = Array.from(
  new Set(catalogItems.map((item) => item.material_family ?? "uncategorized")),
).sort();

export function formatFamily(family: string) {
  return family.replace(/_/g, " ");
}

const findCatalogItem = (manufacturer: string, nameIncludes: string) => {
  const item = catalogItems.find(
    (candidate) =>
      candidate.manufacturer === manufacturer &&
      candidate.name.toLowerCase().includes(nameIncludes.toLowerCase()),
  );

  if (!item) {
    throw new Error(`Missing seeded catalog item: ${manufacturer} ${nameIncludes}`);
  }

  return item;
};

export const regions: MaterialRegion[] = [
  {
    id: "terrazzo-floor",
    label: "Aggregate floor",
    material: "large-format tile / terrazzo look",
    confidence: "High",
    box: { left: 4, top: 67, width: 63, height: 25 },
    note: "Broad floor plane with visible aggregate texture and a cool neutral base. Good candidate for tile or resilient surface alternates.",
    searchIntent: "Cool grey aggregate flooring with quiet contrast and a commercial hospitality feel.",
    included: true,
  },
  {
    id: "walnut-panels",
    label: "Walnut wall panels",
    material: "wood-look laminate / wall surface",
    confidence: "High",
    box: { left: 6, top: 20, width: 28, height: 40 },
    note: "Vertical warm wood grain reads consistently across panels. The search should favor walnut tones and low-sheen finishes.",
    searchIntent: "Warm walnut panels with vertical grain, suitable for wall cladding or millwork.",
    included: true,
  },
  {
    id: "stone-counter",
    label: "Pale counter surface",
    material: "stone-look tile / slab surface",
    confidence: "Medium",
    box: { left: 45, top: 45, width: 35, height: 16 },
    note: "Light stone counter has enough clean surface area to search, though the crop includes edge shadows and reflected light.",
    searchIntent: "Soft white stone surface with subtle movement and honed character.",
    included: true,
  },
  {
    id: "sage-fabric",
    label: "Sage upholstery",
    material: "contract textile",
    confidence: "Medium",
    box: { left: 63, top: 55, width: 22, height: 28 },
    note: "Curved seating gives a reliable color read, while weave detail is partial. Best handled as textile color and texture inspiration.",
    searchIntent: "Muted sage contract upholstery with a soft woven texture.",
    included: true,
  },
];

export const matchesByRegion: Record<string, ProductMatch[]> = {
  "terrazzo-floor": [
    {
      id: "tile-eternal-grey",
      fit: "Best fit",
      item: findCatalogItem("Daltile", "Eternal Grey"),
      reasons: ["cool grey base", "subtle mineral movement", "floor-ready tile format"],
    },
    {
      id: "tile-timeless-white",
      fit: "Close alternate",
      item: findCatalogItem("Daltile", "Timeless White"),
      reasons: ["lighter commercial neutral", "stone-like surface", "clean hospitality palette"],
    },
    {
      id: "entry-abalone",
      fit: "Creative option",
      item: findCatalogItem("Matter Surfaces", "Abalone"),
      reasons: ["textured aggregate read", "durable entry material", "similar cool tone"],
    },
  ],
  "walnut-panels": [
    {
      id: "laminate-sap-walnut",
      fit: "Best fit",
      item: findCatalogItem("Wilsonart", "Sap Walnut"),
      reasons: ["warm walnut tone", "linear grain", "millwork-friendly surface"],
    },
    {
      id: "laminate-continental-walnut",
      fit: "Close alternate",
      item: findCatalogItem("Wilsonart", "Continental Walnut"),
      reasons: ["rich brown color", "continuous woodgrain", "low-sheen wall application"],
    },
    {
      id: "laminate-brushed-walnut",
      fit: "Creative option",
      item: findCatalogItem("Wilsonart", "Brushed Walnut"),
      reasons: ["more dimensional grain", "warmer accent direction", "panel-friendly scale"],
    },
  ],
  "stone-counter": [
    {
      id: "tile-bridal",
      fit: "Best fit",
      item: findCatalogItem("Daltile", "Bridal"),
      reasons: ["soft white base", "subtle surface movement", "stone-inspired finish"],
    },
    {
      id: "tile-brilliant-white",
      fit: "Close alternate",
      item: findCatalogItem("Daltile", "Brilliant White"),
      reasons: ["cleaner white direction", "quiet contrast", "works as slab inspiration"],
    },
    {
      id: "tile-elegant-beige",
      fit: "Creative option",
      item: findCatalogItem("Daltile", "Elegant Beige"),
      reasons: ["warmer hospitality tone", "soft stone read", "pairs with walnut"],
    },
  ],
  "sage-fabric": [
    {
      id: "textile-tropic",
      fit: "Best fit",
      item: findCatalogItem("KB Contract Textiles", "Tropic"),
      reasons: ["muted green cast", "woven contract textile", "soft seating application"],
    },
    {
      id: "carpet-eucalyptus",
      fit: "Close alternate",
      item: findCatalogItem("Interface", "Eucalyptus"),
      reasons: ["sage-green family", "soft commercial texture", "coordinating finish"],
    },
    {
      id: "wallcovering-seafoam",
      fit: "Creative option",
      item: findCatalogItem("Koroseal", "Seafoam"),
      reasons: ["similar color story", "wall surface translation", "adds material variety"],
    },
  ],
};

export const defaultPrompt =
  "Find orderable materials that match the floor, walnut paneling, pale counter surface, and sage upholstery. Favor hospitality-grade finishes with quiet texture.";

export function getRunStages(scenario: RunScenario): RunStage[] {
  if (scenario === "empty") {
    return [
      { label: "Upload image", detail: "Choose a reference image", status: "active" },
      { label: "Find regions", detail: "Waiting for a run", status: "queued" },
      { label: "Match catalog", detail: "Waiting for regions", status: "queued" },
      { label: "Review cart", detail: "Add samples when ready", status: "queued" },
    ];
  }

  if (scenario === "failed") {
    return [
      { label: "Plan concepts", detail: "Request interpreted", status: "complete" },
      { label: "Segment regions", detail: "Service timed out", status: "failed" },
      { label: "Match catalog", detail: "Not started", status: "queued" },
      { label: "Review cart", detail: "Not started", status: "queued" },
    ];
  }

  if (scenario === "planning") {
    return [
      { label: "Plan concepts", detail: "Reading image and request", status: "active" },
      { label: "Segment regions", detail: "Queued", status: "queued" },
      { label: "Match catalog", detail: "Queued", status: "queued" },
      { label: "Review cart", detail: "Waiting for matches", status: "queued" },
    ];
  }

  if (scenario === "matching") {
    return [
      { label: "Plan concepts", detail: "4 material targets selected", status: "complete" },
      { label: "Segment regions", detail: "4 usable regions found", status: "complete" },
      { label: "Match catalog", detail: "Retrieving orderable materials", status: "active" },
      { label: "Review cart", detail: "Waiting for matches", status: "queued" },
    ];
  }

  return [
    { label: "Plan concepts", detail: "4 material targets selected", status: "complete" },
    { label: "Segment regions", detail: "4 usable regions found", status: "complete" },
    { label: "Match catalog", detail: "Product options ready", status: "complete" },
    { label: "Review cart", detail: "Add samples to cart", status: "active" },
  ];
}
