"use client";

import { BookOpen, Check, Loader2, PenLine, ScanSearch, ShieldCheck } from "lucide-react";

import { cn } from "@/lib/utils";

const STAGES: { key: string; label: string; icon: typeof ScanSearch }[] = [
  { key: "classify", label: "Reading the ticket", icon: ScanSearch },
  { key: "retrieve", label: "Pulling from your docs", icon: BookOpen },
  { key: "policy", label: "Checking policy", icon: ShieldCheck },
  { key: "draft", label: "Writing the reply", icon: PenLine },
];

/**
 * Stepper driven by the ENGINE'S REAL stage events over SSE — not a timer.
 * Each check appears when the pipeline actually completes that stage.
 */
export function AnalyzeProgress({
  active,
  current,
}: {
  active: boolean;
  current: string | null;
}) {
  if (!active) return null;
  const currentIdx = Math.max(0, STAGES.findIndex((s) => s.key === current));

  return (
    <ol className="flex flex-col gap-1 py-2">
      {STAGES.map((stage, index) => {
        const done = index < currentIdx;
        const current = index === currentIdx && active;
        return (
          <li
            key={stage.key}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              current && "bg-muted",
              !done && !current && "text-muted-foreground opacity-50",
            )}
          >
            {done ? (
              <Check className="h-4 w-4 text-emerald-400" />
            ) : current ? (
              <Loader2 className="text-primary h-4 w-4 animate-spin" />
            ) : (
              <stage.icon className="h-4 w-4" />
            )}
            <span className={cn(current && "font-medium")}>{stage.label}</span>
            {current ? (
              <span className="text-muted-foreground ml-auto text-xs">
                working…
              </span>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
