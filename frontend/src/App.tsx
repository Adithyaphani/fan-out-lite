import { NavLink, Route, Routes } from "react-router-dom";
import { RunProvider, useRun } from "./run";
import Home from "./pages/Home";
import Upload from "./pages/Upload";
import Concept from "./pages/Concept";
import Storyboard from "./pages/Storyboard";
import Manage from "./pages/Manage";

function TopBar() {
  const { runId } = useRun();
  const dis = runId ? "" : "disabled";
  return (
    <div className="topbar">
      <NavLink to="/" className="brand">
        <span className="dot" />
        Fan-Out <span style={{ color: "var(--primary)" }}>Lite</span>
      </NavLink>
      <nav className="nav">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>Home</NavLink>
        <NavLink to="/upload" className={({ isActive }) => (isActive ? "active" : "")}>Upload</NavLink>
        <NavLink to="/concept" className={({ isActive }) => `${isActive ? "active" : ""} ${dis}`}>Concept</NavLink>
        <NavLink to="/storyboard" className={({ isActive }) => `${isActive ? "active" : ""} ${dis}`}>Storyboard</NavLink>
        <NavLink to="/manage" className={({ isActive }) => `${isActive ? "active" : ""} ${dis}`}>Manage</NavLink>
      </nav>
      <div className="spacer" />
      {runId && <span className="pill"><span className="led" style={{ background: "var(--good)" }} />run {runId}</span>}
    </div>
  );
}

export default function App() {
  return (
    <RunProvider>
      <div className="shell">
        <TopBar />
        <div className="wrap">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/concept" element={<Concept />} />
            <Route path="/storyboard" element={<Storyboard />} />
            <Route path="/manage" element={<Manage />} />
          </Routes>
        </div>
      </div>
    </RunProvider>
  );
}
