import type { CompanySource } from "@/lib/types";

function LinkIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-3 w-3"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M10 14 21 3M21 3h-6M21 3v6M19 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h6" />
    </svg>
  );
}

/** Small inline citation next to a fact, linking to the page(s) it came from. */
export function SourceCite({ sources }: { sources?: CompanySource[] }) {
  if (!sources || sources.length === 0) return null;
  return (
    <details className="group/cite relative inline-block align-middle">
      <summary
        title="Sources"
        className="inline-flex cursor-pointer list-none items-center text-slate-300 hover:text-accent [&::-webkit-details-marker]:hidden"
      >
        <LinkIcon />
      </summary>
      <div className="absolute left-0 top-5 z-10 w-56 rounded-lg border border-slate-200 bg-white p-2 text-xs shadow-lg">
        {sources.slice(0, 4).map((s) => (
          <a
            key={s.id}
            href={s.source_url}
            target="_blank"
            rel="noreferrer"
            className="block truncate rounded px-1.5 py-1 text-slate-600 hover:bg-slate-50 hover:text-accent"
          >
            {s.page_title ?? s.source_url}
          </a>
        ))}
      </div>
    </details>
  );
}
