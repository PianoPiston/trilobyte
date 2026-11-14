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
  const [h, setH] = useState<Health | null>(null);
  useEffect(() => {
    const f = () => api.health().then(setH).catch(() => setH(null));
    f();
    const t = window.setInterval(f, 30000);
    return () => window.clearInterval(t);
  }, []);
  if (!h) return <span className="status off">API offline</span>;
  return h.vlm.online
    ? <span className="status on" title={h.vlm.models.join(", ")}>● AI model online{h.vlm.ft_model ? ` · ${h.vlm.ft_model}` : ""}</span>
    : <span className="status cache" title={h.vlm.reason}>● Exact routes + answer cache (AI model offline)</span>;
}

export default function App() {
  return (
    <div className="app">
      <header className="top">
        <NavLink to="/" className="brand"><span className="logo">▦</span> Trilobyte <span className="brand-sub">Make Blueprints Talk</span></NavLink>
        <nav>
          <NavLink to="/" end>Drawings &amp; upload</NavLink>
          <NavLink to="/search">Search</NavLink>
          <NavLink to="/benchmark">Benchmark</NavLink>
          <NavLink to="/developers">API &amp; MCP</NavLink>
        </nav>
        <span className="grow" />
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
    </div>
  );
}
