import type { PayloadState } from "@/lib/api";

export function StatusNotice({ state }: { state: PayloadState }) {
  if (state.status === "ready") return null;
  if (state.status === "loading") {
    return (
      <p className="mono" role="status" aria-live="polite">
        Loading GridLock analysis…
      </p>
    );
  }
  return (
    <div role="alert" style={{ borderLeft: "2px solid var(--accent)", paddingLeft: 16 }}>
      <p className="mono" style={{ color: "var(--accent)", margin: "0 0 6px" }}>
        {state.message}
      </p>
      {state.detail && (
        <p className="mono-plain" style={{ margin: 0 }}>
          {state.detail}
        </p>
      )}
    </div>
  );
}
