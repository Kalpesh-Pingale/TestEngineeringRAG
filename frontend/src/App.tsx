import React, { useCallback, useEffect, useState } from "react";
import { SyncDashboard } from "./components/SyncDashboard";
import { VectorExplorer } from "./components/VectorExplorer";
import { RAGExplorer } from "./components/RAGExplorer";
import { TestGeneration } from "./components/TestGeneration";
import { HealthPanel } from "./components/HealthPanel";
import { api, Health } from "./api/client";

type Tab = "sync" | "vectors" | "rag" | "tests";

const TABS: { key: Tab; label: string; icon: string; blurb: string }[] = [
  { key: "sync", label: "Sync", icon: "⟳", blurb: "Jira → Vector DB" },
  { key: "vectors", label: "Vector DB", icon: "◈", blurb: "Stored embeddings" },
  { key: "rag", label: "RAG Explorer", icon: "◎", blurb: "Inspect retrieval" },
  { key: "tests", label: "Test Generation", icon: "✓", blurb: "Generate & upload" },
];

function App() {
  const [activeTab, setActiveTab] = useState<Tab>("sync");
  const [health, setHealth] = useState<Health | null>(null);
  const [healthOpen, setHealthOpen] = useState(false);

  const fetchHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
    } catch {
      setHealth({ status: "down", service: "", checks: {} });
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const id = setInterval(fetchHealth, 15000);
    return () => clearInterval(id);
  }, [fetchHealth]);

  const statusTone =
    health?.status === "ok"
      ? { dot: "bg-ok", text: "text-ok", label: "All systems ready" }
      : health?.status === "degraded"
      ? { dot: "bg-warn", text: "text-warn", label: "Setup required" }
      : { dot: "bg-danger", text: "text-danger", label: "Backend unreachable" };

  return (
    <div className="flex min-h-screen bg-canvas">
      {/* Sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-edge bg-surface md:flex">
        <div className="border-b border-edge px-5 py-5">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-strong text-sm font-bold text-white">
              T
            </span>
            <div className="leading-tight">
              <h1 className="text-sm font-semibold text-content">
                Test Engineering
              </h1>
              <p className="text-xs text-content-subtle">RAG Platform</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {TABS.map((t) => {
            const active = activeTab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                aria-current={active ? "page" : undefined}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors ${
                  active
                    ? "bg-brand/10 text-brand"
                    : "text-content-muted hover:bg-surface-overlay hover:text-content"
                }`}
              >
                <span className="w-4 text-center text-sm">{t.icon}</span>
                <span className="flex-1">
                  <span className="block text-sm font-medium">{t.label}</span>
                  <span className="block text-[11px] text-content-subtle">
                    {t.blurb}
                  </span>
                </span>
              </button>
            );
          })}
        </nav>

        {/* Health summary — clicking opens the full diagnostic panel */}
        <button
          onClick={() => setHealthOpen(true)}
          className="m-3 rounded-lg border border-edge bg-surface-overlay px-3 py-2.5 text-left transition-colors hover:border-edge-strong"
        >
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 shrink-0 rounded-full ${statusTone.dot}`} />
            <span className={`text-xs font-semibold ${statusTone.text}`}>
              {statusTone.label}
            </span>
          </div>
          <p className="mt-0.5 text-[11px] text-content-subtle">
            View diagnostics →
          </p>
        </button>

        <p className="border-t border-edge px-5 py-3 text-[11px] text-content-subtle">
          Built by <span className="font-medium text-content-muted">Kalpesh Pingale</span>
        </p>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile tab bar */}
        <nav className="flex gap-1 overflow-x-auto border-b border-edge bg-surface px-3 py-2 md:hidden">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                activeTab === t.key
                  ? "bg-brand/10 text-brand"
                  : "text-content-muted"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {/* Degraded banner — the single most useful thing to surface, since a
            misconfigured embedding model silently ruins every result. */}
        {health && health.status !== "ok" && (
          <button
            onClick={() => setHealthOpen(true)}
            className="flex w-full items-center gap-2 border-b border-warn/30 bg-warn/10 px-6 py-2 text-left text-xs text-warn transition-colors hover:bg-warn/20"
          >
            <span>⚠</span>
            <span className="flex-1">
              {health.status === "down"
                ? "Cannot reach the backend. Is uvicorn running on port 8000?"
                : "Some components need setup — results may be unreliable."}
            </span>
            <span className="font-semibold">Details →</span>
          </button>
        )}

        <main className="mx-auto w-full max-w-7xl flex-1 p-6">
          <div key={activeTab} className="animate-fade-up">
            {activeTab === "sync" && <SyncDashboard />}
            {activeTab === "vectors" && <VectorExplorer />}
            {activeTab === "rag" && <RAGExplorer />}
            {activeTab === "tests" && <TestGeneration />}
          </div>
        </main>

        {/* Byline — the sidebar carries it on desktop, where this is hidden. */}
        <footer className="border-t border-edge px-6 py-3 text-center text-[11px] text-content-subtle md:hidden">
          Built by <span className="font-medium text-content-muted">Kalpesh Pingale</span>
        </footer>
      </div>

      {healthOpen && (
        <HealthPanel
          health={health}
          onClose={() => setHealthOpen(false)}
          onRefresh={fetchHealth}
        />
      )}
    </div>
  );
}

export default App;
