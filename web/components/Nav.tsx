import Link from "next/link";

function Landmark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-6 w-6 text-accent"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M3 21h18" />
      <path d="M4 10h16" />
      <path d="M5 21V10M19 21V10M9 21V10M15 21V10" />
      <path d="M12 3 4 7h16z" />
    </svg>
  );
}

export function Nav() {
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
      <nav className="mx-auto flex max-w-7xl items-center gap-8 px-6 py-5">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold text-ink">
          <Landmark />
          DESCOvery<span className="text-accent">_point</span>
        </Link>
        <div className="flex gap-6 text-base text-slate-600">
          <Link href="/" className="hover:text-accent">
            Home
          </Link>
          <Link href="/settings" className="hover:text-accent">
            Settings
          </Link>
        </div>
        <Link
          href="/funds"
          className="ml-auto inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-base font-medium text-ink shadow-sm transition hover:border-accent hover:text-accent"
        >
          <Landmark />
          PE Fund Library
        </Link>
      </nav>
    </header>
  );
}
