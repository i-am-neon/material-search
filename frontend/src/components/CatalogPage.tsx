import React from "react";
import { ArrowLeft, Layers3 } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { catalogItems, formatFamily, materialFamilies } from "../demoData";

export function CatalogPage() {
  const [activeFamily, setActiveFamily] = React.useState("all");
  const visibleItems =
    activeFamily === "all"
      ? catalogItems
      : catalogItems.filter((item) => (item.material_family ?? "uncategorized") === activeFamily);

  return (
    <main className="app-shell catalog-shell">
      <header className="topbar catalog-topbar">
        <Link className="brand-mark" to="/" aria-label="Back to workbench">
          <ArrowLeft size={22} />
        </Link>
        <div>
          <p className="eyebrow">Demo Catalog</p>
          <h1>Material swatch catalog</h1>
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
          <p className="eyebrow">Seeded Records</p>
          <strong>{catalogItems.length}</strong>
        </div>
        <div>
          <p className="eyebrow">Image Rule</p>
          <strong>square swatches</strong>
        </div>
        <div>
          <p className="eyebrow">Visible</p>
          <strong>{visibleItems.length}</strong>
        </div>
      </section>

      <nav className="catalog-filters" aria-label="Catalog material families">
        <button className={activeFamily === "all" ? "active" : ""} onClick={() => setActiveFamily("all")}>
          All
        </button>
        {materialFamilies.map((family) => (
          <button
            className={activeFamily === family ? "active" : ""}
            key={family}
            onClick={() => setActiveFamily(family)}
          >
            {formatFamily(family)}
          </button>
        ))}
      </nav>

      <section className="catalog-grid" aria-label="Catalog swatches">
        {visibleItems.map((item) => (
          <article className="catalog-card" key={item.image_object_key}>
            <a
              className="catalog-swatch"
              href={item.metadata.source_url}
              rel="noreferrer"
              target="_blank"
            >
              {item.image_url ? <img src={item.image_url} alt={`${item.manufacturer} ${item.name}`} /> : null}
            </a>
            <div className="catalog-card-body">
              <div>
                <p>{item.manufacturer}</p>
                <h2>{item.name}</h2>
              </div>
              <div className="catalog-card-meta">
                <span>{formatFamily(item.material_family ?? "uncategorized")}</span>
                {item.metadata.colorway ? <span>{item.metadata.colorway}</span> : null}
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
