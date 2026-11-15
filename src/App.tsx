import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api";
import type { Health } from "./api";
import Browse from "./pages/Browse";
import DrawingView from "./pages/DrawingView";
import Search from "./pages/Search";
import Benchmark from "./pages/Benchmark";
import Developers from "./pages/Developers";

function ModelStatus() {
  const [h, setH] = useState<Health | null | undefined>();
  useEffect(() => {
    const load = () => api.health().then(setH).catch(() => setH(null));
    load();
    const t = window.setInterval(load, 30000);
    return () => window.clearInterval(t);
  }, []);
  if (h === undefined) return null;
  if (h === null) return <span className="status off">API offline</span>;
  return h.vlm.online
    ? <span className="status on" title={h.vlm.models.join(", ")}>Model online</span>
    : <span className="status cache" title={h.vlm.reason}>Model offline<span className="status-detail"> · exact routes and cached answers</span></span>;
}

export default function App() {
  return (
    <>
      <header className="top">
        <NavLink to="/" className="brand">Trilobyte</NavLink>
        <nav>
          <NavLink to="/" end>Drawings</NavLink>
          <NavLink to="/search">Search</NavLink>
          <NavLink to="/benchmark">Benchmark</NavLink>
          <NavLink to="/developers">API</NavLink>
        </nav>
        <ModelStatus />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Browse />} />
          <Route path="/d/:id" element={<DrawingView />} />
          <Route path="/search" element={<Search />} />
          <Route path="/benchmark" element={<Benchmark />} />
          <Route path="/developers" element={<Developers />} />
        </Routes>
      </main>
    </>
  );
}
