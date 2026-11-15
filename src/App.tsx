import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api";
import type { Health } from "./api";
import Browse from "./pages/Browse";
import DrawingView from "./pages/DrawingView";
import Search from "./pages/Search";
import Benchmark from "./pages/Benchmark";
import Developers from "./pages/Developers";

function Logo() {
  return (
    <svg className="logo" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.5c4.4 0 7.5 3.4 7.5 8.5 0 6-3.2 10.5-7.5 10.5S4.5 17 4.5 11c0-5.1 3.1-8.5 7.5-8.5Z" fill="currentColor" />
      <path d="M5.6 9.5h12.8M5 13h14M6.4 16.5h11.2M12 9.5v11" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

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
    ? <span className="status on" title={h.vlm.models.join(", ")}>Model online{h.vlm.ft_model && <span className="status-detail"> · {h.vlm.ft_model}</span>}</span>
    : <span className="status cache" title={h.vlm.reason}>Model offline<span className="status-detail"> · exact routes and cached answers</span></span>;
}

export default function App() {
  return (
    <>
      <header className="top">
        <NavLink to="/" className="brand" aria-label="Trilobyte"><Logo />Trilobyte</NavLink>
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
