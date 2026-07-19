const TONES: Record<string, string> = {
  slate: "bg-slate-100 text-slate-700",
  green: "bg-green-100 text-green-800",
  amber: "bg-amber-100 text-amber-800",
  blue: "bg-blue-100 text-blue-800",
  red: "bg-red-100 text-red-800",
};

export function Badge({
  children,
  tone = "slate",
}: {
  children: React.ReactNode;
  tone?: keyof typeof TONES | string;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${TONES[tone] ?? TONES.slate}`}
    >
      {children}
    </span>
  );
}
