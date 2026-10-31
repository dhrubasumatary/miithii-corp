"use client";

import { KeyRound } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
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
      if (!ok) throw new Error("That key didn't work");
      localStorage.setItem(KEY_STORAGE, input.trim());
      setKey(input.trim());
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} — engine at ${ENGINE_URL} reachable?`
          : "Verification failed",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-svh items-center justify-center overflow-hidden p-6">
      {/* the floor steps up around the panel — a quiet light behind it */}
      <div
        aria-hidden
        className="pointer-events-none absolute top-1/3 left-1/2 h-[480px] w-[720px] -translate-x-1/2 rounded-full opacity-[0.07]"
        style={{ background: "radial-gradient(closest-side, #3E63DD, transparent)" }}
      />
      <div className="relative w-full max-w-sm">
        <div className="mb-7 flex flex-col items-center gap-3 text-center">
          <img
            src="/miithii-mark.svg"
            alt="MIITHII"
            className="h-12 w-12 rounded-xl"
          />
          <div>
            <h1 className="text-lg font-semibold tracking-tight">MIITHII</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              Draft support replies from your own docs.
            </p>
          </div>
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
          className="bg-card rounded-2xl border p-6"
          style={{
            boxShadow:
              "inset 0 0 0 1px rgb(255 255 255 / 0.04), 0 8px 30px rgb(0 0 0 / 0.35)",
          }}
        >
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="api-key" className="flex items-center gap-1.5">
                <KeyRound className="h-3.5 w-3.5" />
                Workspace key
              </Label>
              <Input
                id="api-key"
                type="password"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="mii_…"
                autoFocus
              />
            </div>
            {error ? <p className="text-destructive text-sm">{error}</p> : null}
            <Button type="submit" disabled={busy || !input.trim()}>
              {busy ? "Checking…" : "Open MIITHII"}
            </Button>
          </div>
        </form>

        <p className="text-muted-foreground mt-5 text-center text-xs">
          Every draft waits for a person. Nothing sends itself.
        </p>
      </div>
    </div>
  );
}

export function resetKey() {
  localStorage.removeItem(KEY_STORAGE);
  window.location.reload();
}
