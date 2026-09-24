import { lazy, Suspense, useState } from "react";
import {
  NavLink,
  Route,
  Routes,
  Link,
  useMatch,
  useNavigate,
  useLocation,
} from "react-router-dom";
import {
  Activity,
  ArrowDownToLine,
  BookOpen,
  ChartNoAxesCombined,
  CheckCheck,
  CircleDot,
  FlaskConical,
  LayoutDashboard,
  ListFilter,
  Menu,
  Moon,
  Plus,
  ShieldCheck,
  Sun,
  X,
} from "lucide-react";
import { useRun, useRuns, isTerminal } from "./api";
import { cn, Loading, Status } from "./components";

const Setup = lazy(() => import("./pages/Setup"));
const Analysis = lazy(() => import("./pages/Analysis"));
const Overview = lazy(() =>
  import("./pages/Workspace").then((m) => ({ default: m.Overview })),
);
const Live = lazy(() =>
  import("./pages/Workspace").then((m) => ({ default: m.Live })),
);
const Methodology = lazy(() =>
  import("./pages/Workspace").then((m) => ({ default: m.Methodology })),
);

export default function App() {
  const match = useMatch("/runs/:runId/*");
  const runId = match?.params.runId || "";
  const run = useRun(runId);
  const runs = useRuns();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobile, setMobile] = useState(false);
  const [dark, setDark] = useState(
    () => localStorage.getItem("decisionlab-theme") === "dark",
  );
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  const nav = [
    ["results", "Results", ChartNoAxesCombined],
    ["reliability", "Reliability", ShieldCheck],
    ["robustness", "Robustness", CheckCheck],
    ["cases", "Cases", ListFilter],
    ["methodology", "Methodology", BookOpen],
  ] as const;
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      {mobile && (
        <button
          className="mobile-shade"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={cn("sidebar", mobile && "open")}>
        <Link to="/" className="brand" onClick={() => setMobile(false)}>
          <span className="brand-mark">
            <FlaskConical size={21} />
          </span>
          <span>
            Decision<span className="brand-light">Lab</span>
          </span>
        </Link>
        <button
          className="icon-button mobile-close"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        >
          <X size={20} />
        </button>
        <div className="workspace-label">
          <CircleDot size={13} /> Local workspace
        </div>
        <nav aria-label="Main navigation" onClick={() => setMobile(false)}>
          <NavLink to="/" end>
            <LayoutDashboard size={18} />
            Overview
          </NavLink>
          <NavLink to="/new">
            <Plus size={18} />
            New evaluation
          </NavLink>
          <div className="nav-divider" />
          <span className="nav-label">Evaluation</span>
          {runId ? (
            <NavLink to={"/runs/" + runId + "/live"}>
              <Activity size={18} />
              Live run
              {run.data && !isTerminal(run.data.status) && (
                <i className="live-dot" />
              )}
            </NavLink>
          ) : (
            <span className="nav-disabled">
              <Activity size={18} />
              Live run
            </span>
          )}
          {nav.map(([path, name, Icon]) =>
            runId ? (
              <NavLink
                key={path}
                to={
                  "/runs/" +
                  runId +
                  "/" +
                  path +
                  (path === "methodology" ? "" : location.search)
                }
              >
                <Icon size={18} />
                {name}
              </NavLink>
            ) : (
              <span key={path} className="nav-disabled">
                <Icon size={18} />
                {name}
              </span>
            ),
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="method-note">
            <ShieldCheck size={17} />
            <strong>Evidence over rankings</strong>
            <p>
              Same cases. Separate tracks.
              <br />
              Every outcome traceable.
            </p>
          </div>
          <button
            className="theme-button"
            onClick={() => {
              localStorage.setItem(
                "decisionlab-theme",
                dark ? "light" : "dark",
              );
              setDark(!dark);
            }}
          >
            {dark ? <Sun size={16} /> : <Moon size={16} />}{" "}
            {dark ? "Light appearance" : "Dark appearance"}
          </button>
          <span className="version">
            DecisionLab 0.1 <span>Local</span>
          </span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb">
              Workspace <span>/</span>{" "}
              {runId
                ? "Evaluation"
                : location.pathname === "/new"
                  ? "New evaluation"
                  : "Overview"}
            </span>
          </div>
          <div className="topbar-right">
            {runId && (
              <>
                <label className="sr-only" htmlFor="run-select">
                  Selected evaluation
                </label>
                <select
                  id="run-select"
                  className="run-select"
                  value={runId}
                  onChange={(e) =>
                    navigate("/runs/" + e.target.value + "/results")
                  }
                >
                  {runs.data?.items.map((r) => (
                    <option value={r.run_id} key={r.run_id}>
                      {r.name}
                    </option>
                  ))}
                </select>
                {run.data && (
                  <>
                    <span className="badge">
                      {run.data.track === "default"
                        ? "Default"
                        : "Production-tuned"}
                    </span>
                    <Status value={run.data.status} />
                    {isTerminal(run.data.status) && (
                      <a
                        className="button secondary small"
                        aria-label="Export bundle"
                        href={"/api/v1/runs/" + runId + "/exports/bundle"}
                      >
                        <ArrowDownToLine size={15} />
                        <span>Export bundle</span>
                      </a>
                    )}
                  </>
                )}
              </>
            )}
            <span className="local-indicator">
              <i /> On your machine
            </span>
          </div>
        </header>
        <main id="main">
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/new" element={<Setup />} />
              <Route path="/runs/:runId/live" element={<Live />} />
              <Route
                path="/runs/:runId/methodology"
                element={<Methodology />}
              />
              <Route path="/runs/:runId/:view" element={<Analysis />} />
              <Route
                path="*"
                element={
                  <div className="empty">
                    <h1>Page not found</h1>
                    <Link to="/">Return to overview</Link>
                  </div>
                }
              />
            </Routes>
          </Suspense>
        </main>
        <footer className="footer">
          <span>Paired decisions. Reproducible evidence.</span>
          <span>
            Jev <i className="model-dot jev" /> Laya{" "}
            <i className="model-dot laya" />
          </span>
        </footer>
      </div>
    </div>
  );
}
