"use client";

import { ArrowUpRight, RefreshCw, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { ActionBadge, FlagBadges } from "@/components/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { EngineError, engine } from "@/lib/engine";
import type { AnalysisResult, TicketRow } from "@/lib/engine";

export default function TicketsPage() {
  const [tickets, setTickets] = useState<TicketRow[]>([]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      setTickets(await engine.listTickets());
    } catch (err) {
      if (err instanceof EngineError && err.status === 401) resetKeyAndToast();
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function analyze() {
    if (!subject.trim() || !body.trim()) {
      setError("Both subject and message are required.");
      return;
    }
    setAnalyzing(true);
    setError("");
    setResult(null);
    try {
      const analysis = await engine.createTicket(subject.trim(), body.trim());
      setResult(analysis);
      toast.success(`Analyzed — action: ${analysis.action.replaceAll("_", " ")}`);
      await refresh();
      setSubject("");
      setBody("");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Analysis failed unexpectedly";
      setError(message);
      toast.error(message);
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Tickets</h1>
          <p className="text-muted-foreground text-sm">
            Submit a customer ticket — MIITHII classifies it, applies policy,
            and drafts a response.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refresh()}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>New ticket</CardTitle>
          <CardDescription>
            Live analysis typically takes 10–45 seconds.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Input
            placeholder="Subject — e.g. Production API is down"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            maxLength={500}
            disabled={analyzing}
          />
          <Textarea
            placeholder="Paste the customer's message here…"
            value={body}
            onChange={(event) => setBody(event.target.value)}
            rows={5}
            maxLength={10000}
            disabled={analyzing}
          />
          {error ? <p className="text-destructive text-sm">{error}</p> : null}
          <Button
            onClick={() => void analyze()}
            disabled={analyzing || !subject.trim() || !body.trim()}
            className="self-start"
          >
            {analyzing ? (
              <>
                <Send className="h-4 w-4 animate-pulse" />
                Analyzing…
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                Analyze ticket
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {result ? (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Analysis</CardTitle>
                <CardDescription>
                  {result.category.replaceAll("_", " ")} · {result.severity} ·{" "}
                  {result.confidence != null
                    ? `${Math.round(result.confidence * 100)}% confidence`
                    : null}
                  {result.latency_ms != null
                    ? ` · ${(result.latency_ms / 1000).toFixed(1)}s`
                    : null}
                </CardDescription>
              </div>
              <ActionBadge action={result.action} />
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <FlagBadges flags={result.policy_flags} />
            <div className="rounded-md border bg-muted/40 p-4 text-sm whitespace-pre-wrap">
              {result.answer ?? "No response generated."}
            </div>
            {result.citations.length ? (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground text-xs">sources:</span>
                {result.citations.map((citation) => (
                  <Badge key={citation} variant="outline">
                    {citation}
                  </Badge>
                ))}
              </div>
            ) : null}
            {result.requires_human ? (
              <p className="text-red-400 text-sm">
                Human review required — do not send without an employee reading
                this.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Queue</CardTitle>
          <CardDescription>
            Most recent tickets — click a row for the full audit trail.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Subject</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Created</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {tickets.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className="text-muted-foreground py-8 text-center"
                  >
                    No tickets yet.
                  </TableCell>
                </TableRow>
              ) : (
                tickets.map((ticket) => (
                  <TicketSheetRow key={ticket.id} ticket={ticket} />
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function TicketSheetRow({ ticket }: { ticket: TicketRow }) {
  const [analyses, setAnalyses] = useState<Awaited<
    ReturnType<typeof engine.analyses>
  > | null>(null);
  const [open, setOpen] = useState(false);

  async function load() {
    setOpen(true);
    setAnalyses(null);
    try {
      setAnalyses(await engine.analyses(ticket.id));
    } catch {
      setAnalyses([]);
    }
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger render={<TableRow className="cursor-pointer" onClick={() => void load()} />}>
          <TableCell className="max-w-md truncate font-medium">
            {ticket.subject}
          </TableCell>
          <TableCell>
            <Badge variant="outline">{ticket.status}</Badge>
          </TableCell>
          <TableCell className="text-right text-muted-foreground text-xs">
            {new Date(ticket.created_at).toLocaleString()}
          </TableCell>
          <TableCell>
            <ArrowUpRight className="h-4 w-4 text-muted-foreground" />
          </TableCell>
      </SheetTrigger>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{ticket.subject}</SheetTitle>
          <SheetDescription>Audit trail — every analysis run</SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-4 p-4">
          {analyses === null ? (
            <p className="text-muted-foreground text-sm">Loading…</p>
          ) : analyses.length === 0 ? (
            <p className="text-muted-foreground text-sm">No analyses.</p>
          ) : (
            analyses.map((analysis) => (
              <Card key={analysis.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <ActionBadge action={analysis.action} />
                    <span className="text-muted-foreground text-xs">
                      {new Date(analysis.created_at).toLocaleString()}
                    </span>
                  </div>
                  <CardDescription className="text-xs">
                    {analysis.category.replaceAll("_", " ")} ·{" "}
                    {analysis.provider}/{analysis.model}
                    {analysis.latency_ms != null
                      ? ` · ${(analysis.latency_ms / 1000).toFixed(1)}s`
                      : null}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-2">
                  <FlagBadges flags={analysis.policy_flags} />
                  <p className="text-sm whitespace-pre-wrap">
                    {analysis.answer ?? "—"}
                  </p>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function resetKeyAndToast() {
  toast.error("API key rejected — connect again.");
}
