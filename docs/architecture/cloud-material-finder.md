# Cloud Material Finder Architecture

```mermaid
%%{init: {"flowchart": {"diagramPadding": 24}}}%%
flowchart TB
    classDef input fill:#eef6ff,stroke:#3b82f6,color:#0f172a
    classDef queue fill:#fff7ed,stroke:#ea580c,color:#0f172a
    classDef compute fill:#fef3c7,stroke:#d97706,color:#0f172a
    classDef storage fill:#ecfdf5,stroke:#059669,color:#0f172a
    classDef output fill:#f5f3ff,stroke:#7c3aed,color:#0f172a

    subgraph catalog_indexing["Offline: Catalog Indexing"]
        direction LR
        catalog_source["Catalog Import\nmetadata + product photos"]
        catalog_queue["Catalog Indexing Queue\nasync embed/upsert jobs"]
        catalog_worker["Catalog Worker\nruns embed/upsert jobs"]
    end

    subgraph search_workflow["Online: Material Search Request"]
        direction LR
        user_request["User Image + Search Request"]
        web_app["Vite + React Web App\nupload + status + results UI"]
        api["App API\nstores upload + creates run"]
        search_queue["Search Job Queue\nasync run dispatch"]
        search_worker["Search Worker\nruns queued search jobs"]
        orchestrator["LangGraph Orchestrator\nowns material search workflow"]
        matches["Matched Catalog Products"]
    end

    subgraph model_services["Model Services"]
        direction LR
        gemini["Gemini API\ngemini-3.5-flash"]
        sam3["SAM3 Hosting\nModal GPU endpoint"]
        embedding_service["Vision Embedding Service\nSigLIP 2"]
    end

    subgraph data_layer["Shared Data Layer"]
        direction TB
        image_storage["Supabase Storage\ncatalog + uploaded image objects"]
        pgvector["Supabase Postgres + pgvector\nrun state + metadata + vectors"]
    end

    catalog_source -- upload images --> image_storage
    catalog_source -- product records --> catalog_queue
    catalog_queue --> catalog_worker
    catalog_worker -- catalog images --> embedding_service
    embedding_service -- catalog embedding versions --> pgvector
    image_storage -- image keys / URLs --> pgvector

    user_request --> web_app
    web_app -- submit search / fetch run status --> api
    api -- image key + request text --> search_queue
    api -- run record --> pgvector
    api -- status + result reads --> pgvector
    search_queue --> search_worker
    search_worker --> orchestrator
    orchestrator -- planning + region review --> gemini
    orchestrator -- image + concepts --> sam3
    orchestrator -- material crops --> embedding_service
    embedding_service -- query embeddings --> pgvector
    pgvector -- top matches --> matches
    orchestrator -- progress + final result --> pgvector

    class catalog_source,user_request input
    class catalog_queue,search_queue queue
    class catalog_worker,web_app,api,search_worker,orchestrator,gemini,sam3,embedding_service compute
    class image_storage,pgvector storage
    class matches output
```

## Notes

- This diagram is the target architecture for the rewrite, not a map of the current toy implementation.
- Postgres should store stable image URLs or object keys, not image bytes.
- Prefer `google/siglip2-so400m-patch14-384` over the original OpenAI CLIP model for material-image retrieval.
- Embedding model changes create incompatible vector spaces. Reindex by adding a new embedding version, not by blindly overwriting existing vectors.
- A useful target shape is `catalog_items` for product metadata and `catalog_item_embeddings` for `{ catalog_item_id, model_id, dimensions, embedding, created_at }`.

## Chosen Stack

- Frontend: Vite + React + TypeScript.
- App API: FastAPI with Pydantic schemas for request/response contracts.
- Orchestration: LangGraph inside Python workers; Pydantic for typed graph state and structured model outputs.
- Queues: Dramatiq + Redis, with coarse-grained jobs for search runs and catalog indexing.
- Data: Supabase Postgres + pgvector for run state, catalog metadata, embeddings, and match results.
- Object storage: Supabase Storage for catalog images, uploaded images, and generated crop/mask artifacts.
- Model services: Gemini API for multimodal planning, Modal-hosted SAM3 for segmentation, and SigLIP 2 for image embeddings.

## Model Choices

- Use `gemini-3.5-flash` for the planner/selector. It is the current stable Flash model and fits the need for fast multimodal reasoning over the room image, user request, and SAM3 region candidates.
- Use SAM3 for segmentation because the system needs precise boxes/masks for open-vocabulary material concepts. The LLM decides what to ask for; SAM3 produces the spatial evidence.
- Use SigLIP 2 for material retrieval because the catalog and query crops need to share one modern image-embedding space. The same model version should embed both catalog photos and user-image crops.
- Keep the trust boundary explicit: models can choose concepts, regions, and descriptions, but code owns persisted IDs, boxes, confidence scores, embeddings, nearest-neighbor search, product IDs, and similarity values.

## LLM Decides Intent, Code Owns Evidence

The LLM is responsible for interpreting the user's natural-language request and
the reference image into material targets, SAM3 prompts, priorities, and
explanatory intent. Code is responsible for evidence: persisted run IDs,
planned target rows, SAM3 boxes/masks/scores, crop artifacts, embedding vectors,
catalog item IDs, similarity values, and final stored results. Negative
preferences such as "avoid anything too glossy" should first be captured as
planner metadata; they should only affect filtering/ranking once
there is explicit evidence in catalog metadata or retrieval signals.

Follow-up note: add planner evals later for constraint handling, including a
case like "Find materials like the floor and green seating, but avoid anything
too glossy."

## Future Result Deduping

Current matching should preserve raw evidence: if SAM3 returns multiple regions
for one planned target, each region is cropped, embedded, matched, and persisted
as its own `material_search_regions` row with its own ranked
`material_search_matches`. Do not merge those region records before retrieval;
separate regions are useful for debugging, provenance, and region-level UI.

A future product-facing dedupe layer can sit on top of those raw region match
sets. For regions that share a planned `target_id`, group matches by
`catalog_item_id`, keep the best similarity as the displayed score, and preserve
the per-region provenance behind it:

```text
target_id: chair
catalog_item_id: material-a
best_similarity: 0.91
best_region_id: chair__sam3_region_1
region_hits:
  - region_id: chair__sam3_region_1, similarity: 0.91, rank: 1
  - region_id: chair__sam3_region_2, similarity: 0.88, rank: 1
```

Recommended first-pass ranking: sort by best similarity, then by the number of
same-target regions that matched the item, then by best rank. If recurring
evidence across multiple regions needs to matter more, add only a small bounded
boost so one excellent crop can still outrank several weak matches.

This is distinct from deduping SAM3 regions themselves. Catalog-result deduping
uses stable product IDs and is safe to present as "this material matched multiple
regions." Region deduping would require box or mask IoU and should be treated as
a separate segmentation-quality feature.

## Future Product Assembly Segmentation

The first material-search path should keep SAM3 prompts short, visual, and
surface-oriented. That works for material retrieval, but it is not enough for
catalog items whose sellable product boundary is a whole assembly rather than a
single continuous visible surface. For example, a prompt like `sink` may segment
only the vessel bowl because that is the clearest visual grounding for the word,
while a catalog sink product may include faucet, handles, drain hardware, and
other disconnected components.

Do not rely on a single compound SAM3 prompt such as `sink with faucet and
handles` to define this product boundary. SAM3 should still receive concrete
visual prompts, while application code owns the catalog product grouping. A
future product-mode planner can expand one catalog target into component prompts:

```text
catalog target: sink
component SAM3 prompts:
  - vessel sink bowl
  - sink faucet
  - sink handles
  - sink drain
```

The segmentation layer can then union the component regions into one logical
catalog-object region. A simple box union works without masks, but it can include
background between disconnected parts. A mask union is preferable when
`include_masks=true`: decode each component mask, OR the masks together, compute
the enclosing box, and persist a synthetic region such as `sink__union` while
retaining the component regions for provenance and debugging.

This product assembly mode should remain separate from material-surface search.
The same image may need both modes: `beige stone vessel sink` for material
matching, and `sink` as a product assembly for whole-item catalog matching.

## Scalability

- Treat each material search as a durable run, not a one-off in-memory request.
  - The API creates a `run_id`, stores the uploaded image key and request text, enqueues work, and lets the client poll status.
  - Persist key outputs as the graph advances: selected concepts, SAM3 regions, crop/mask keys, catalog matches, status, errors, and final summary.
  - A useful target shape is `material_search_runs`, `material_search_regions`, and `material_search_matches`.
  - Postgres is the durable memory of the run; LangGraph owns the workflow while the worker is executing it.
- Start with coarse-grained queues: one job per catalog indexing unit and one job per user search run. LangGraph manages the steps inside a search run.
  - This keeps the first version easier to reason about while the product path is still being proven.
  - At much higher traffic, each LangGraph node could become its own queue job so segmentation, LLM planning, crop embedding, and pgvector search can scale independently.
  - Node-level queueing would also improve retries and backpressure because SAM3 GPU work, LLM calls, and embedding work have different latency, cost, and failure modes.
  - The tradeoff is extra state serialization, idempotency requirements, more queues, and harder debugging.
