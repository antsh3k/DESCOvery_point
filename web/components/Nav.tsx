import Link from "next/link";

export function Nav() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <nav className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-4">
        <Link href="/" className="font-semibold text-ink">
          thesis<span className="text-accent">_match</span>
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
