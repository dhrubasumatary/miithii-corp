"use client";

import { BookOpen, KeyRound, Loader2, Ticket } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

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

  return (
    <div className="flex min-h-svh">
      <aside className="fixed inset-y-0 left-0 z-10 flex w-60 flex-col border-r bg-sidebar">
        <div className="flex h-14 items-center gap-2 border-b px-5">
          {/* miithii-corpo corporate mark (original work, this repo) */}
          <img src="/miithii-mark.svg" alt="" className="h-6 w-6 rounded-md" />
          <span className="font-semibold tracking-tight">MIITHII</span>
          <span className="text-muted-foreground text-xs">copilot</span>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                pathname.startsWith(link.href)
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
              )}
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto p-3">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start text-muted-foreground"
            onClick={resetKey}
          >
            <KeyRound className="h-4 w-4" />
            Change API key
          </Button>
        </div>
      </aside>
      <main className="ml-60 flex-1 p-6">{checking ? null : children}</main>
      {checking ? (
        <div className="ml-60 flex flex-1 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : null}
    </div>
  );
}
