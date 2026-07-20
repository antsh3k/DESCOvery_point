import type { ProgressEvent } from "@/lib/types";

/**
 * Live activity trail for the ingest pipeline. Each entry is a completed
 * milestone; while `active`, the most recent entry renders as in-progress
 * (pulsing) since it's the stage currently running.
 */
export function ActivityFeed({
  progress,
  active,
  failed,
}: {
  progress: ProgressEvent[];
  active: boolean;
  failed?: boolean;
}) {
  if (progress.length === 0) return null;
  const lastIndex = progress.length - 1;

  return (
    <ol className="space-y-0">
      {progress.map((ev, i) => {
        const isLast = i === lastIndex;
        const running = active && isLast;
        return (
          <li key={`${ev.at}-${i}`} className="flex gap-3">
            {/* marker + connector */}
            <div className="flex flex-col items-center">
              <Dot running={running} failed={failed && isLast} />
              {!isLast && <span className="w-px flex-1 bg-slate-200" />}
            </div>
            <div className={`pb-4 ${isLast ? "" : "opacity-70"}`}>
              <p
                className={`text-sm ${
                  running ? "font-medium text-ink" : "text-slate-600"
                }`}
              >
                {ev.label}
                {running && <span className="ml-1 animate-pulse">…</span>}
              </p>
              {ev.detail && (
                <p className="mt-0.5 text-xs text-slate-400">{ev.detail}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Dot({ running, failed }: { running: boolean; failed?: boolean }) {
  if (failed) {
    return (
      <span className="mt-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white">
        ✕
      </span>
    );
  }
  if (running) {
    return (
      <span className="mt-1 flex h-3.5 w-3.5 items-center justify-center">
        <span className="absolute h-3.5 w-3.5 animate-ping rounded-full bg-accent/40" />
        <span className="h-2.5 w-2.5 rounded-full bg-accent" />
      </span>
    );
  }
  return (
    <span className="mt-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-accent/15 text-[9px] font-bold text-accent">
      ✓
    </span>
  );
}
