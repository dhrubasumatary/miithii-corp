"use client";

import { ArrowUpRight, Check, Copy, Mic, RefreshCw, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ActionBadge, FlagBadges } from "@/components/badges";
import { AnalyzeProgress } from "@/components/analyze-progress";
import { FadeUp } from "@/components/motion";
import { EmptyState, TableSkeleton } from "@/components/data-states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { VoiceFace } from "@/components/voice-face";
import {
  useVoiceInput,
  useVoiceInputSupported,
} from "@/lib/use-voice-input";
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
import { latency, relativeTime } from "@/lib/format";
import { AppShell } from "@/components/app-shell";
import { KeyGate } from "@/components/key-gate";
import { EngineError, engine } from "@/lib/engine";
import type { AnalysisResult, TicketRow } from "@/lib/engine";

export default function TicketsPage() {
  const [tickets, setTickets] = useState<TicketRow[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [stage, setStage] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const voiceSupported = useVoiceInputSupported();

  /* The transcript is an append, never an overwrite — dictated words join
     whatever was already typed, separated the way a sentence would be. */
  const voice = useVoiceInput({
    onTranscript: (text) => {
      setBody((current) =>
        current.trim() ? `${current.trimEnd()} ${text}` : text,
      );
      setTimeout(() => bodyRef.current?.focus(), 0);
    },
  });

  const refresh = useCallback(async () => {
    try {
      setTickets(await engine.listTickets());
    } catch {
      // 401 is handled globally (auto gate); anything else stays quiet
    } finally {
      setLoaded(true);
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
    setCopied(false);
    setStage("classify");
    try {
      let analysis: AnalysisResult;
      try {
        analysis = await engine.createTicketStream(subject.trim(), body.trim(), (s) =>
          setStage(s),
        );
      } catch (streamErr) {
        // stream path failed (proxy buffering, engine hiccup) — the plain
        // endpoint does the same work without stage events
        if (streamErr instanceof EngineError && streamErr.status === 401) throw streamErr;
        analysis = await engine.createTicket(subject.trim(), body.trim());
      }
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
      setStage(null);
    }
  }

  async function copyDraft() {
    if (!result?.answer) return;
    await navigator.clipboard.writeText(result.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <KeyGate>
    <AppShell>
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Tickets</h1>
          <p className="text-muted-foreground text-sm">
            Paste what the customer sent. You get a draft grounded in your docs.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refresh()}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <FadeUp delay={0.04}>
      <Card>
        <CardHeader>
          <CardTitle>Draft a reply</CardTitle>
          <CardDescription>
            Ctrl+Enter to run.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Input
            placeholder="Subject — e.g. Production API is down"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && event.ctrlKey) void analyze();
            }}
            maxLength={500}
            disabled={analyzing}
          />
          {voice.status !== "idle" ? (
            <VoiceFace voice={voice} />
          ) : (
            <div className="flex flex-col gap-1">
              <Textarea
                ref={bodyRef}
                placeholder="What did the customer say? (Ctrl+Enter to run)"
                value={body}
                onChange={(event) => setBody(event.target.value)}
                rows={5}
                maxLength={10000}
                disabled={analyzing}
                className="well resize-none"
              />
              <div className="flex items-center justify-between">
                {voiceSupported ? (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Dictate the message with your voice"
                    title="Dictate with your voice"
                    onClick={voice.start}
                    disabled={analyzing}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <Mic className="h-4 w-4" />
                  </Button>
                ) : (
                  <span />
                )}
                <span className="text-muted-foreground text-xs">
                  {body.length}/10,000
                </span>
              </div>
            </div>
          )}
          {error ? <p className="text-destructive text-sm">{error}</p> : null}
          <Button
            onClick={() => void analyze()}
            disabled={analyzing || !subject.trim() || !body.trim()}
            className="self-start transition-transform active:scale-[0.98]"
          >
            <Send className="h-4 w-4" />
            {analyzing ? "Drafting…" : "Draft reply"}
          </Button>
        </CardContent>
      </Card>
      </FadeUp>

      {analyzing ? (
        <Card>
          <CardHeader>
            <CardTitle>Working on it</CardTitle>
            <CardDescription>
              Usually 10–45 seconds depending on provider load.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AnalyzeProgress active={analyzing} current={stage} />
          </CardContent>
        </Card>
      ) : null}

      {result && !analyzing ? (
        <FadeUp>
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Draft</CardTitle>
                <CardDescription>
                  {result.category.replaceAll("_", " ")} · {result.severity}
                  {result.confidence != null
                    ? ` · ${Math.round(result.confidence * 100)}% confidence`
                    : null}
                  {latency(result.latency_ms)
                    ? ` · ${latency(result.latency_ms)}`
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
            <div className="flex flex-wrap items-center justify-between gap-3">
              {result.citations.length ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-muted-foreground text-xs">
                    sources:
                  </span>
                  {result.citations.map((citation) => (
                    <Badge key={citation} variant="outline">
                      {citation}
                    </Badge>
                  ))}
                </div>
              ) : (
                <span />
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => void copyDraft()}
                disabled={!result.answer}
              >
                {copied ? (
                  <Check className="h-4 w-4 text-emerald-400" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
                {copied ? "Copied" : "Copy draft"}
              </Button>
            </div>
            {result.requires_human ? (
              <p className="text-sm text-red-400">
                Needs a human read before this goes out.
              </p>
            ) : null}
          </CardContent>
        </Card>
        </FadeUp>
      ) : null}

      <FadeUp delay={0.08}>
      <Card>
        <CardHeader>
          <CardTitle>Queue</CardTitle>
          <CardDescription>
            Everything you&apos;ve run. Click a row for its trail.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!loaded ? (
            <TableSkeleton />
          ) : tickets.length === 0 ? (
            <EmptyState
              icon="tickets"
              title="No tickets yet"
              description="Your first draft will land in this queue."
            />
          ) : (
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
                {tickets.map((ticket) => (
                  <TicketSheetRow key={ticket.id} ticket={ticket} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      </FadeUp>
    </div>
    </AppShell>
    </KeyGate>
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
      <SheetTrigger
        render={<TableRow className="cursor-pointer" onClick={() => void load()} />}
      >
        <TableCell className="max-w-md truncate font-medium">
          {ticket.subject}
        </TableCell>
        <TableCell>
          <Badge variant="outline">{ticket.status}</Badge>
        </TableCell>
        <TableCell className="text-muted-foreground text-right text-xs">
          {relativeTime(ticket.created_at)}
        </TableCell>
        <TableCell>
          <ArrowUpRight className="text-muted-foreground h-4 w-4" />
        </TableCell>
      </SheetTrigger>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{ticket.subject}</SheetTitle>
          <SheetDescription>Audit trail — every analysis run</SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-4 p-4">
          {analyses === null ? (
            <div className="flex flex-col gap-3">
              <div className="bg-muted h-24 animate-pulse rounded-md" />
              <div className="bg-muted h-24 animate-pulse rounded-md" />
            </div>
          ) : analyses.length === 0 ? (
            <p className="text-muted-foreground text-sm">No analyses.</p>
          ) : (
            analyses.map((analysis) => (
              <Card key={analysis.id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <ActionBadge action={analysis.action} />
                    <span className="text-muted-foreground text-xs">
                      {relativeTime(analysis.created_at)}
                    </span>
                  </div>
                  <CardDescription className="text-xs">
                    {analysis.category.replaceAll("_", " ")} ·{" "}
                    {analysis.provider}/{analysis.model}
                    {latency(analysis.latency_ms)
                      ? ` · ${latency(analysis.latency_ms)}`
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
