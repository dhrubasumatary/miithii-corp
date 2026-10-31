"use client";

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
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Connect to MIITHII</CardTitle>
          <CardDescription>
            Paste a tenant API key. Engine: {ENGINE_URL}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="api-key">API key</Label>
            <Input
              id="api-key"
              type="password"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && save()}
              placeholder="mii_..."
            />
          </div>
          {error ? <p className="text-destructive text-sm">{error}</p> : null}
          <Button onClick={save} disabled={busy || !input.trim()}>
            {busy ? "Verifying…" : "Connect"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export function resetKey() {
  localStorage.removeItem(KEY_STORAGE);
  window.location.reload();
}
