import Link from "next/link";

function Landmark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-5 w-5 text-accent"
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
      <nav className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-4">
        <Link href="/" className="flex items-center gap-2 font-semibold text-ink">
          <Landmark />
          DESCOvery<span className="text-accent">_point</span>
        </Link>
        <div className="flex gap-4 text-sm text-slate-600">
          <Link href="/" className="hover:text-accent">
            Analyze
          </Link>
          <Link href="/funds" className="hover:text-accent">
            Funds
          </Link>
          <Link href="/settings" className="hover:text-accent">
            Settings
          </Link>
        </div>
      </nav>
    </header>
  );
}
