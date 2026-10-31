"use client";

import {
  ArrowUpRight,
  Check,
  Copy,
  FileText,
  Mic,
  Receipt,
  RefreshCw,
  Send,
  ShieldAlert,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ActionBadge, actionLabel, FlagBadges } from "@/components/badges";
import { AnalyzeProgress } from "@/components/analyze-progress";
import { FadeUp } from "@/components/motion";
import { EmptyState, TableSkeleton } from "@/components/data-states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { VoiceFace } from "@/components/voice-face";
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
import {
  useVoiceInput,
  useVoiceInputSupported,
} from "@/lib/use-voice-input";

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
      toast.success(`Reply ready — ${actionLabel(analysis.action).toLowerCase()}`);
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
    setTimeout(() => setCopied(false), 2500);
  }

  return (
    <KeyGate>
    <AppShell>
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Tickets</h1>
          <p className="text-muted-foreground text-sm">
            Paste what the customer sent. The reply comes from your docs —
            you send it.
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
          <CardTitle>New reply</CardTitle>
          <CardDescription>
            Ctrl+Enter to run — takes about 15 seconds.
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
            {analyzing ? "Writing…" : "Write the reply"}
          </Button>

          {/* The wait is part of the reply's arrival, not a separate
              chapter — no card, no "provider load", just the engine's
              real stages ticking past. */}
          {analyzing ? <AnalyzeProgress active={analyzing} current={stage} /> : null}

          {result && !analyzing ? (
            <ReplyResult result={result} copied={copied} onCopy={() => void copyDraft()} />
          ) : null}
        </CardContent>
      </Card>
      </FadeUp>

      <FadeUp delay={0.08}>
      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
          <CardDescription>
            Every ticket you&apos;ve run. Click a row for its full trail.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!loaded ? (
            <TableSkeleton />
          ) : tickets.length === 0 ? (
            <EmptyState
              icon="tickets"
              title="Nothing here yet"
              description="The first reply you write will land in this queue."
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

/* The reply, the receipt, and the handoff — one section, because this is
   where the run ends. The receipt is the landing page's promise made real:
   the same rows the hero shows (action, flags, measured spend), now with
   the actual numbers this run produced. */
function ReplyResult({
  result,
  copied,
  onCopy,
}: {
  result: AnalysisResult;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="border-border flex flex-col gap-5 border-t pt-5">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-sm font-medium">
            <Send className="text-primary h-4 w-4" />
            The reply
          </span>
          <ActionBadge action={result.action} />
        </div>
        <div className="well rounded-lg p-4 text-[15px] leading-relaxed whitespace-pre-wrap">
          {result.answer ?? "No response generated."}
        </div>
        {result.requires_human ? (
          <p className="flex items-center gap-1.5 text-sm text-red-400">
            <ShieldAlert className="h-4 w-4" />
            Needs a human read before this goes out.
          </p>
        ) : null}
      </div>

      {result.citations.length ? (
        <div className="flex flex-wrap items-center gap-1.5">
          {result.citations.map((citation) => (
            <span
              key={citation}
              className="border-border bg-muted/40 text-muted-foreground inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs"
            >
              <FileText className="h-3 w-3" />
              {citation}
            </span>
          ))}
        </div>
      ) : null}

      <ReceiptRows result={result} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-muted-foreground text-xs">
          Nothing sends itself — the reply is yours to send.
        </span>
        <Button
          onClick={onCopy}
          disabled={!result.answer}
          className="transition-transform active:scale-[0.98]"
        >
          {copied ? (
            <Check className="h-4 w-4" />
          ) : (
            <Copy className="h-4 w-4" />
          )}
          {copied ? "Copied — yours to send" : "Copy for sending"}
        </Button>
      </div>
    </div>
  );
}

/* Same row language as the hero demo's receipt panel: key muted on the
   left, value on the right, hairline between. Numbers only when the run
   actually produced them. */
function ReceiptRows({ result }: { result: AnalysisResult }) {
  const tokens =
    result.prompt_tokens != null || result.completion_tokens != null
      ? `${(result.prompt_tokens ?? 0).toLocaleString()} in · ${(result.completion_tokens ?? 0).toLocaleString()} out`
      : null;
  const latencyLabel = latency(result.latency_ms);
  return (
    <div className="flex flex-col gap-1.5 text-xs">
      <div className="text-muted-foreground flex items-center gap-2 font-medium">
        <Receipt className="h-3.5 w-3.5" />
        Receipt
      </div>
      <Row k="category" v={result.category.replaceAll("_", " ")} />
      <Row k="action" v={actionLabel(result.action)} />
      <Row
        k="flags"
        v={
          result.policy_flags.length
            ? result.policy_flags.map((f) => f.replaceAll("_", " ")).join(", ")
            : "none"
        }
      />
      {result.confidence != null ? (
        <Row k="confidence" v={`${Math.round(result.confidence * 100)}%`} />
      ) : null}
      {latencyLabel ? <Row k="latency" v={latencyLabel} /> : null}
      {tokens ? <Row k="tokens" v={tokens} /> : null}
      {result.cost_usd != null ? <Row k="cost" v={`$${result.cost_usd.toFixed(4)}`} /> : null}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between border-b border-white/5 pb-1.5">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-medium">{v}</span>
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
                    {analysis.cost_usd != null
                      ? ` · $${analysis.cost_usd.toFixed(4)}`
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
