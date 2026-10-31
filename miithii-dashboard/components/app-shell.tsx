"use client";

import { BookOpen, KeyRound, Loader2, Ticket } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "motion/react";

import { resetKey } from "@/components/key-gate";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/tickets", label: "Tickets", icon: Ticket },
  { href: "/knowledge", label: "Knowledge", icon: BookOpen },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [checking, setChecking] = useState(true);

  // brief delay so the key gate doesn't flash before hydration
  useEffect(() => {
    const timer = setTimeout(() => setChecking(false), 150);
    return () => clearTimeout(timer);
  }, []);

  const nav = (vertical: boolean) => (
    <>
      {LINKS.map((link) => {
        const active = pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              vertical && "w-full",
              active
                ? "text-sidebar-accent-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {active ? (
              <motion.span
                layoutId="nav-pill"
                className="bg-sidebar-accent absolute inset-0 rounded-md"
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              />
            ) : null}
            <link.icon className="relative z-10 h-4 w-4" />
            <span className="relative z-10">{link.label}</span>
          </Link>
        );
      })}
    </>
  );

  return (
    <div className="flex min-h-svh">
      {/* mobile top bar */}
      <header className="fixed inset-x-0 top-0 z-20 flex h-14 items-center gap-3 border-b bg-sidebar px-4 md:hidden">
        <img src="/miithii-mark.svg" alt="" className="h-6 w-6 rounded-md" />
        <span className="font-semibold tracking-tight">MIITHII</span>
        <nav className="ml-auto flex items-center gap-1">{nav(false)}</nav>
      </header>
      {/* desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-10 hidden w-60 flex-col border-r bg-sidebar md:flex">
        <div className="flex h-14 items-center gap-2 border-b px-5">
          {/* miithii-corpo corporate mark (original work, this repo) */}
          <img src="/miithii-mark.svg" alt="" className="h-6 w-6 rounded-md" />
          <span className="font-semibold tracking-tight">MIITHII</span>
          <span className="text-muted-foreground text-xs">copilot</span>
        </div>
        <nav className="flex flex-col gap-1 p-3">{nav(true)}</nav>
        <div className="mt-auto p-3">
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground w-full justify-start"
            onClick={resetKey}
          >
            <KeyRound className="h-4 w-4" />
            Change API key
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-4 pt-18 md:ml-60 md:p-6">
        {checking ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
          </div>
        ) : (
          children
        )}
      </main>
    </div>
  );
}
