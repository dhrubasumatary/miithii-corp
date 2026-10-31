const ACTION_STYLES: Record<string, string> = {
  answer: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  human_review: "border-red-500/30 bg-red-500/10 text-red-400",
  escalate: "border-red-500/30 bg-red-500/10 text-red-400",
  refuse_and_escalate: "border-red-500/30 bg-red-500/10 text-red-400",
  refuse: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  refuse_and_guide: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  clarify: "border-sky-500/30 bg-sky-500/10 text-sky-400",
};

export function ActionBadge({ action }: { action: string }) {
  const style =
    ACTION_STYLES[action] ?? "border-border bg-muted text-muted-foreground";
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${style}`}
    >
      {action.replaceAll("_", " ")}
    </span>
  );
}

export function FlagBadges({ flags }: { flags: string[] }) {
  if (!flags.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {flags.map((flag) => (
        <span
          key={flag}
          className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-xs text-red-400"
        >
          {flag.replaceAll("_", " ")}
        </span>
      ))}
    </div>
  );
}
