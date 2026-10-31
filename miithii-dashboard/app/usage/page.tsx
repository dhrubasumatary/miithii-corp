"use client";

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { TableSkeleton } from "@/components/data-states";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { engine } from "@/lib/engine";
import type { UsageSummary } from "@/lib/engine";

export default function UsagePage() {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setUsage(await engine.usage());
    } catch {
      toast.error("Could not load usage.");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const totals = usage?.totals;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Usage & cost</h1>
          <p className="text-muted-foreground text-sm">
            What the engine spent these two weeks.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refresh()}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {!loaded ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="bg-muted h-28 animate-pulse rounded-xl" />
          <div className="bg-muted h-28 animate-pulse rounded-xl" />
          <div className="bg-muted h-28 animate-pulse rounded-xl" />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Analyses</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">{totals?.events ?? 0}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Tokens</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">
                {((totals?.prompt_tokens ?? 0) + (totals?.completion_tokens ?? 0)).toLocaleString()}
              </p>
              <p className="text-muted-foreground text-xs">
                {totals?.prompt_tokens ?? 0} in · {totals?.completion_tokens ?? 0} out
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Estimated cost</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">
                ${(totals?.cost_usd ?? 0).toFixed(4)}
              </p>
              <p className="text-muted-foreground text-xs">
                measured per request, not estimated
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Daily</CardTitle>
          <CardDescription>Per-day consumption from usage_events.</CardDescription>
        </CardHeader>
        <CardContent>
          {!loaded ? (
            <TableSkeleton />
          ) : !usage?.days.length ? (
            <p className="text-muted-foreground py-8 text-center text-sm">
              Nothing spent yet.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Day</TableHead>
                  <TableHead className="text-right">Events</TableHead>
                  <TableHead className="text-right">Tokens</TableHead>
                  <TableHead className="text-right">Cost (USD)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usage.days.map((day) => (
                  <TableRow key={day.day}>
                    <TableCell className="font-medium">{day.day}</TableCell>
                    <TableCell className="text-right">{day.events}</TableCell>
                    <TableCell className="text-right">
                      {(day.prompt_tokens + day.completion_tokens).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      ${day.cost_usd.toFixed(4)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
