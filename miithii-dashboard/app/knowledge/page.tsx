"use client";

import { Globe, RefreshCw, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { EmptyState, TableSkeleton } from "@/components/data-states";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { engine } from "@/lib/engine";
import type { KnowledgeRow } from "@/lib/engine";

const STATUS_STYLES: Record<string, string> = {
  ready: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  pending: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  failed: "border-red-500/30 bg-red-500/10 text-red-400",
};

export default function KnowledgePage() {
  const [sources, setSources] = useState<KnowledgeRow[]>([]);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setSources(await engine.listKnowledge());
    } catch {
      toast.error("Could not load knowledge sources.");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Knowledge</h1>
          <p className="text-muted-foreground text-sm">
            Everything MIITHII knows comes from here — answers cite these
            documents.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refresh()}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <Tabs defaultValue="upload">
        <TabsList>
          <TabsTrigger value="upload">
            <Upload className="h-4 w-4" />
            Upload
          </TabsTrigger>
          <TabsTrigger value="crawl">
            <Globe className="h-4 w-4" />
            Crawl web
          </TabsTrigger>
        </TabsList>

        <TabsContent value="upload">
          <UploadCard onDone={refresh} />
        </TabsContent>
        <TabsContent value="crawl">
          <CrawlCard onDone={refresh} />
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle>Sources</CardTitle>
          <CardDescription>
            {loaded && sources.length > 0
              ? `${sources.length} document${sources.length === 1 ? "" : "s"} ingested.`
              : "Chunked and embedded on ingest — status shows live progress."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!loaded ? (
            <TableSkeleton />
          ) : sources.length === 0 ? (
            <EmptyState
              icon="knowledge"
              title="MIITHII knows nothing yet"
              description="Upload a policy doc or crawl your help center — every answer is built from what lands here."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Chunks</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sources.map((source) => (
                  <TableRow key={source.id}>
                    <TableCell className="max-w-sm truncate font-medium">
                      {source.title}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {source.kind}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`rounded-md border px-2 py-0.5 text-xs ${STATUS_STYLES[source.status] ?? ""}`}
                      >
                        {source.status}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {source.chunks}
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

function UploadCard({ onDone }: { onDone: () => Promise<void> }) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      const result = await engine.uploadKnowledge(title.trim(), content);
      if (result.status === "ready") {
        toast.success(`Ingested: ${title.trim()}`);
        setTitle("");
        setContent("");
        await onDone();
      } else {
        toast.error(`Ingest failed: ${result.error ?? "unknown error"}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload a document</CardTitle>
        <CardDescription>
          Markdown or plain text — chunked and embedded on ingest.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="doc-title">Title</Label>
          <Input
            id="doc-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. Refund policy v2"
            maxLength={500}
            disabled={busy}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="doc-content">Content</Label>
          <Textarea
            id="doc-content"
            value={content}
            onChange={(event) => setContent(event.target.value)}
            rows={8}
            placeholder="Paste the document text…"
            disabled={busy}
          />
        </div>
        <Button
          className="self-start"
          onClick={() => void submit()}
          disabled={busy || !title.trim() || !content.trim()}
        >
          <Upload className="h-4 w-4" />
          {busy ? "Ingesting…" : "Ingest document"}
        </Button>
      </CardContent>
    </Card>
  );
}

function CrawlCard({ onDone }: { onDone: () => Promise<void> }) {
  const [url, setUrl] = useState("");
  const [pages, setPages] = useState(5);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      const result = await engine.crawlKnowledge(url.trim(), pages);
      const ready = result.ingested.filter((s) => s.status === "ready").length;
      toast.success(`Crawled ${result.ingested.length} pages — ${ready} ready`);
      setUrl("");
      await onDone();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Crawl failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Crawl a help center</CardTitle>
        <CardDescription>
          A page URL, or a sitemap (.xml) — up to 10 pages per run, embedded
          automatically.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="crawl-url">URL</Label>
          <Input
            id="crawl-url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://help.example.com or https://help.example.com/sitemap.xml"
            disabled={busy}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="crawl-pages">Max pages (sitemap only)</Label>
          <Input
            id="crawl-pages"
            type="number"
            min={1}
            max={10}
            value={pages}
            onChange={(event) => setPages(Number(event.target.value) || 5)}
            disabled={busy}
          />
        </div>
        <Button
          className="self-start"
          onClick={() => void submit()}
          disabled={busy || !url.trim()}
        >
          <Globe className="h-4 w-4" />
          {busy ? "Crawling…" : "Start crawl"}
        </Button>
      </CardContent>
    </Card>
  );
}
