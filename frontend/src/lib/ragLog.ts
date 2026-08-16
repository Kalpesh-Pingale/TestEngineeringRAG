/**
 * In-browser activity log for RAG operations.
 *
 * Every RAG call is recorded here — start, outcome, duration, and the numbers
 * that explain a bad result (chunks retrieved, best similarity, tokens). The
 * single-query trace in RAG Explorer shows *one* call in depth; this shows the
 * sequence, which is what you need when quality drifts between calls or a
 * request fails intermittently.
 *
 * Deliberately client-side and ephemeral: it survives tab switches and reloads
 * within a session, and disappears when the tab closes. Nothing is sent anywhere.
 */

export type RagLogLevel = "pending" | "success" | "error";

export interface RagLogEntry {
  id: string;
  /** epoch ms — rendered as a wall-clock time */
  ts: number;
  level: RagLogLevel;
  /** short operation name, e.g. "rag.query" */
  op: string;
  /** one-line human summary */
  summary: string;
  /** wall-clock duration of the call, once it has finished */
  durationMs?: number;
  /** key/value pairs rendered as chips under the summary */
  detail?: Record<string, string | number>;
}

const STORAGE_KEY = "ter.ragLog";
/** Cap the buffer — this is a debugging aid, not an audit trail. */
const MAX_ENTRIES = 100;

let entries: RagLogEntry[] = load();
const listeners = new Set<() => void>();

function load(): RagLogEntry[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as RagLogEntry[]) : [];
  } catch {
    return [];
  }
}

function persist() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    /* private mode or quota — the log still works in memory */
  }
}

function emit() {
  persist();
  listeners.forEach((fn) => fn());
}

let seq = 0;

export const ragLog = {
  /** Newest first. A stable reference between emits, as useSyncExternalStore requires. */
  getSnapshot: () => entries,

  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },

  /** Record the start of a call; returns its id so it can be settled later. */
  start(op: string, summary: string, detail?: RagLogEntry["detail"]): string {
    const id = `${Date.now().toString(36)}-${seq++}`;
    const entry: RagLogEntry = {
      id,
      ts: Date.now(),
      level: "pending",
      op,
      summary,
      detail,
    };
    entries = [entry, ...entries].slice(0, MAX_ENTRIES);
    emit();
    return id;
  },

  /** Settle a started call as success or error. */
  settle(
    id: string,
    level: Exclude<RagLogLevel, "pending">,
    summary: string,
    durationMs: number,
    detail?: RagLogEntry["detail"]
  ) {
    entries = entries.map((e) =>
      e.id === id
        ? { ...e, level, summary, durationMs, detail: { ...e.detail, ...detail } }
        : e
    );
    emit();
  },

  clear() {
    entries = [];
    emit();
  },
};
