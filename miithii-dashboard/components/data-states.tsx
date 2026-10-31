"use client";

import { BookOpen, Inbox, Sparkles } from "lucide-react";
import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/** Designed loading state for data tables (skill: never ship bare loaders). */
export function TableSkeleton({ rows = 4, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {Array.from({ length: cols }).map((_, i) => (
            <TableHead key={i}>
              <Skeleton className="h-3 w-16" />
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: rows }).map((_, r) => (
          <TableRow key={r}>
            {Array.from({ length: cols }).map((_, c) => (
              <TableCell key={c}>
                <Skeleton className="h-4" style={{ width: `${45 + ((r * 7 + c * 13) % 40)}%` }} />
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

/** Designed empty state: icon, message, and a way out. */
export function EmptyState({
  icon,
  title,
  description,
  cta,
}: {
  icon: "tickets" | "knowledge";
  title: string;
  description: string;
  cta?: { label: string; href: string };
}) {
  const Icon = icon === "tickets" ? Inbox : BookOpen;
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <div className="bg-primary/10 text-primary flex h-12 w-12 items-center justify-center rounded-xl">
        <Icon className="h-6 w-6" />
      </div>
      <div>
        <p className="font-medium">{title}</p>
        <p className="text-muted-foreground mt-1 max-w-sm text-sm">{description}</p>
      </div>
      {cta ? (
        <Link
          href={cta.href}
          className="text-primary text-sm font-medium hover:underline"
        >
          {cta.label}
        </Link>
      ) : (
        <p className="text-muted-foreground flex items-center gap-1.5 text-xs">
          <Sparkles className="h-3.5 w-3.5" />
          Everything MIITHII answers will show up here.
        </p>
      )}
    </div>
  );
}
