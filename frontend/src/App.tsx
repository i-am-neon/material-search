import { HashRouter, Route, Routes } from "react-router-dom";
import { CatalogPage } from "./components/CatalogPage";
import { Sam3Playground } from "./components/Sam3Playground";
import { SearchWorkbench } from "./components/SearchWorkbench";

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<SearchWorkbench initialScenario="empty" />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/sam3-playground" element={<Sam3Playground />} />
      </Routes>
    </HashRouter>
  );
}
