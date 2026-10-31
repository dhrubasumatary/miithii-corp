"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
        err instanceof Error ? `${err.message} — engine: ${ENGINE_URL}` : "Verification failed",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-svh flex-col items-center justify-center overflow-hidden p-6">
      <div
        aria-hidden
        className="pointer-events-none absolute top-1/4 left-1/2 h-[560px] w-[820px] -translate-x-1/2 rounded-full opacity-[0.10]"
        style={{ background: "radial-gradient(closest-side, #3E63DD, transparent)" }}
      />
      <div className="relative flex w-full max-w-2xl flex-col items-center gap-7 text-center">
        <img src="/miithii-mark.svg" alt="MIITHII" className="h-11 w-11 rounded-xl" />

        <h1 className="text-4xl font-semibold leading-tight tracking-tight md:text-5xl">
          Support drafts that{" "}
          <span className="text-[#6B84FF]">actually know</span> your product
        </h1>
        <p className="text-muted-foreground text-lg">
          Grounded in your docs. Checked by your rules. Sent by you.
        </p>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
          className="flex w-full max-w-md items-center gap-2"
        >
          <Input
            type="password"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Workspace key — mii_…"
            autoFocus
            className="well h-11 flex-1"
          />
          <Button type="submit" disabled={busy || !input.trim()} className="h-11">
            {busy ? "Checking…" : "Open"}
          </Button>
        </form>
        {error ? <p className="text-destructive text-sm">{error}</p> : null}

        <p className="text-muted-foreground text-xs">
          মিথি — to understand. Every draft waits for a person.
        </p>
      </div>
    </div>
  );
}

export function resetKey() {
  localStorage.removeItem(KEY_STORAGE);
  window.location.reload();
}
