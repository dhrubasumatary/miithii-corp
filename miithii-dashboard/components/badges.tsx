import { cn } from "@/lib/utils";

/* Policy actions in the product's own voice. The engine's taxonomy verbs
   (refuse_and_guide) are for code; people read "Refused, guided". A colored
   dot carries the verdict — boxes and borders make a status report of what
   should read like a word with an opinion. */
const ACTIONS: Record<string, { label: string; dot: string }> = {
  answer: { label: "Answer", dot: "bg-emerald-400" },
  human_review: { label: "Human review", dot: "bg-red-400" },
  escalate: { label: "Escalated", dot: "bg-red-400" },
  refuse_and_escalate: { label: "Refused, escalated", dot: "bg-red-400" },
  refuse: { label: "Refused", dot: "bg-amber-400" },
  refuse_and_guide: { label: "Refused, guided", dot: "bg-amber-400" },
  clarify: { label: "Needs clarity", dot: "bg-sky-400" },
};

export function actionLabel(action: string): string {
  return ACTIONS[action]?.label ?? action.replaceAll("_", " ");
}

export function ActionBadge({ action }: { action: string }) {
  const meta = ACTIONS[action];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium">
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", meta?.dot ?? "bg-muted-foreground")} />
      {actionLabel(action)}
    </span>
  );
}

export function FlagBadges({ flags }: { flags: string[] }) {
  if (!flags.length) return null;
  return (
    <div className="flex flex-wrap gap-2.5">
      {flags.map((flag) => (
        <span
          key={flag}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-red-400"
        >
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" />
          {flag.replaceAll("_", " ")}
        </span>
      ))}
    </div>
  );
}
