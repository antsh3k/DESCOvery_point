import type { CompanySource } from "@/lib/types";

import { Badge } from "./Badge";

export function SourceList({ sources }: { sources: CompanySource[] }) {
  if (sources.length === 0) {
    return <p className="text-sm text-slate-500">No sources captured.</p>;
  }
  return (
    <ul className="space-y-2">
      {sources.map((s) => (
        <li key={s.id} className="text-sm">
          <div className="flex items-center gap-2">
            <a
              href={s.source_url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-accent hover:underline"
            >
              {s.page_title ?? s.source_url}
            </a>
            <Badge tone="slate">{s.fetch_method}</Badge>
          </div>
          {s.snippet && (
            <p className="mt-0.5 line-clamp-2 text-slate-500">{s.snippet}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
