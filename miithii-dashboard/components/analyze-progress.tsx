"use client";

import { BookOpen, Check, Loader2, PenLine, ScanSearch, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const STEPS = [
  { label: "Classifying ticket", icon: ScanSearch },
  { label: "Applying support policy", icon: ShieldCheck },
  { label: "Retrieving knowledge", icon: BookOpen },
  { label: "Drafting response", icon: PenLine },
];

/**
 * Perceived-progress stepper shown while the real analysis runs.
 * Advances on a timer (the pipeline is a single call), then the result
 * replaces it — the wait feels engineered instead of hung.
 */
export function AnalyzeProgress({ active }: { active: boolean }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!active) {
      setStep(0);
      return;
    }
    const timer = setInterval(
      () => setStep((s) => Math.min(s + 1, STEPS.length - 1)),
      3500,
    );
    return () => clearInterval(timer);
  }, [active]);

  if (!active) return null;

  return (
    <ol className="flex flex-col gap-1 py-2">
      {STEPS.map((entry, index) => {
        const done = index < step;
        const current = index === step;
        return (
          <li
            key={entry.label}
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
              <entry.icon className="h-4 w-4" />
            )}
            <span className={cn(current && "font-medium")}>{entry.label}</span>
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
