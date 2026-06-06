import { HashRouter, Route, Routes } from "react-router-dom";
import { CatalogPage } from "./components/CatalogPage";
import { SearchWorkbench } from "./components/SearchWorkbench";

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<SearchWorkbench initialScenario="empty" />} />
        <Route path="/catalog" element={<CatalogPage />} />
      </Routes>
    </HashRouter>
  );
}
