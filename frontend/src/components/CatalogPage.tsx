import React from "react";
import { ArrowLeft, Layers3, Search } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { catalogItems, formatFamily } from "../demoData";
import type { CatalogSeedItem } from "../types";

export function CatalogPage() {
  const [activeCategory, setActiveCategory] = React.useState("all");
  const [query, setQuery] = React.useState("");
  const categoryCounts = React.useMemo(() => buildCategoryCounts(catalogItems), []);
  const categories = React.useMemo(() => Array.from(categoryCounts.keys()).sort(), [categoryCounts]);
  const visibleItems = React.useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return catalogItems.filter((item) => {
      const category = catalogCategory(item);
      const matchesCategory = activeCategory === "all" || category === activeCategory;
      const matchesQuery =
        !normalizedQuery ||
        [
          item.manufacturer,
          item.name,
          item.material_family ?? "",
          category,
          ...(item.metadata.visual_tags ?? []),
        ]
          .join(" ")
          .toLowerCase()
          .includes(normalizedQuery);
      return matchesCategory && matchesQuery;
    });
  }, [activeCategory, query]);
  const curatedItems = catalogItems.filter((item) => item.metadata.import_strategy);

  return (
    <main className="app-shell catalog-shell">
      <header className="topbar catalog-topbar">
        <Link className="brand-mark" to="/" aria-label="Back to workbench">
          <ArrowLeft size={22} />
        </Link>
        <div>
          <p className="eyebrow">Demo Catalog</p>
          <h1>Curated material catalog</h1>
        </div>
        <div className="topbar-actions">
          <NavLink className="nav-action" to="/">
            <Layers3 size={18} />
            <span>Workbench</span>
          </NavLink>
        </div>
      </header>

      <section className="catalog-summary">
        <div>
          <p className="eyebrow">Records</p>
          <strong>{catalogItems.length}</strong>
        </div>
        <div>
          <p className="eyebrow">Curated MB</p>
          <strong>{curatedItems.length}</strong>
        </div>
        <div>
          <p className="eyebrow">Categories</p>
          <strong>{categories.length}</strong>
        </div>
        <div>
          <p className="eyebrow">Visible</p>
          <strong>{visibleItems.length}</strong>
        </div>
      </section>

      <section className="catalog-tools" aria-label="Catalog controls">
        <label className="catalog-search">
          <Search size={16} />
          <span className="sr-only">Search catalog</span>
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search brand, product, category, tag..."
            type="search"
            value={query}
          />
        </label>
        <p>
          Showing {visibleItems.length} of {catalogItems.length}. Product photos are fit-contain so
          object samples stay legible.
        </p>
      </section>

      <nav className="catalog-filters" aria-label="Catalog categories">
        <button className={activeCategory === "all" ? "active" : ""} onClick={() => setActiveCategory("all")}>
          All <span>{catalogItems.length}</span>
        </button>
        {categories.map((category) => (
          <button
            className={activeCategory === category ? "active" : ""}
            key={category}
            onClick={() => setActiveCategory(category)}
          >
            {category} <span>{categoryCounts.get(category)}</span>
          </button>
        ))}
      </nav>

      <section className="catalog-grid" aria-label="Catalog swatches">
        {visibleItems.map((item) => (
          <article className="catalog-card" key={item.image_object_key}>
            <div className="catalog-swatch">
              {item.image_url ? (
                <img src={item.image_url} alt={`${item.manufacturer} ${item.name}`} loading="lazy" />
              ) : null}
            </div>
            <div className="catalog-card-body">
              <div>
                <p>{item.manufacturer}</p>
                <h2>{item.name}</h2>
              </div>
              <div className="catalog-card-meta">
                <span>{catalogCategory(item)}</span>
                <span>{formatFamily(item.material_family ?? "uncategorized")}</span>
                {item.metadata.colorway ? <span>{item.metadata.colorway}</span> : null}
                {item.metadata.source_rank ? <span>#{item.metadata.source_rank}</span> : null}
              </div>
              {item.metadata.visual_tags?.length ? (
                <div className="catalog-tags">
                  {item.metadata.visual_tags.slice(0, 4).map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>
              ) : null}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}

function catalogCategory(item: CatalogSeedItem) {
  return item.metadata.source_category ?? formatFamily(item.material_family ?? "uncategorized");
}

function buildCategoryCounts(items: CatalogSeedItem[]) {
  const counts = new Map<string, number>();
  for (const item of items) {
    const category = catalogCategory(item);
    counts.set(category, (counts.get(category) ?? 0) + 1);
  }
  return counts;
}
