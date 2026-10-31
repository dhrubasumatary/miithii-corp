"use client";

import { KeyRound, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

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
import { ENGINE_URL, KEY_STORAGE, engine } from "@/lib/engine";

export function KeyGate({ children }: { children: React.ReactNode }) {
  const [key, setKey] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setKey(localStorage.getItem(KEY_STORAGE));
    setReady(true);
  }, []);

  if (!ready) return null;

  if (key) return <>{children}</>;

  async function save() {
    if (!input.trim()) return;
    setBusy(true);
    setError("");
    try {
      const ok = await engine.verifyKey(input.trim());
      if (!ok) throw new Error("Engine rejected this key");
      localStorage.setItem(KEY_STORAGE, input.trim());
      setKey(input.trim());
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} — is the engine running at ${ENGINE_URL}?`
          : "Verification failed",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          {/* miithii-corpo corporate mark (original work, this repo) */}
          <img
            src="/miithii-mark.svg"
            alt="MIITHII"
            className="h-14 w-14 rounded-xl"
          />
          <div>
            <h1 className="text-xl font-semibold tracking-tight">MIITHII</h1>
            <p className="text-muted-foreground text-sm">
              Your support team's copilot — every answer policy-checked,
              knowledge-backed, and fully audited.
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Connect your workspace</CardTitle>
            <CardDescription>
              Paste a tenant API key — it stays in this browser and talks only
              to your engine.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="api-key" className="flex items-center gap-1.5">
                <KeyRound className="h-3.5 w-3.5" />
                API key
              </Label>
              <Input
                id="api-key"
                type="password"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && save()}
                placeholder="mii_…"
                autoFocus
              />
            </div>
            {error ? <p className="text-destructive text-sm">{error}</p> : null}
            <Button onClick={save} disabled={busy || !input.trim()}>
              {busy ? "Verifying…" : "Enter dashboard"}
            </Button>
            <div className="text-muted-foreground flex items-start gap-2 text-xs">
              <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Keys are hashed server-side; revoking one cuts access instantly.
              No key? Run{" "}
              <code className="bg-muted rounded px-1 font-mono">
                uv run python scripts/seed_demo.py
              </code>
            </div>
          </CardContent>
        </Card>

        <p className="text-muted-foreground mt-6 flex items-center justify-center gap-1.5 text-xs">
          <Sparkles className="h-3.5 w-3.5" />
          Drafts are suggestions — a human always sends the final word.
        </p>
      </div>
    </div>
  );
}

export function resetKey() {
  localStorage.removeItem(KEY_STORAGE);
  window.location.reload();
}
