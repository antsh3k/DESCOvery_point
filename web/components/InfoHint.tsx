// A small "ⓘ" affordance that reveals explanatory text on hover/focus, via the
// native title tooltip. Used to surface how a pillar's score is calculated
// without cluttering the label.
export function InfoHint({ text }: { text: string }) {
  return (
    <span
      title={text}
      aria-label={text}
      tabIndex={0}
      className="ml-1 inline-flex h-3.5 w-3.5 shrink-0 cursor-help items-center justify-center rounded-full border border-slate-300 text-[9px] font-semibold normal-case leading-none text-slate-400"
    >
      i
    </span>
  );
}
