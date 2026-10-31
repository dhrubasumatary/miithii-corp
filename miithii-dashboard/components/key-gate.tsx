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
    <div className="relative min-h-svh overflow-hidden">
      {/* depth: floor gradient + brand glow behind the product window */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -10%, rgb(62 99 221 / 0.25), transparent), radial-gradient(ellipse 60% 40% at 50% 110%, rgb(62 99 221 / 0.18), transparent), #0B1120",
        }}
      />

      <div className="relative mx-auto flex max-w-4xl flex-col items-center px-6 pb-24 pt-24 text-center">
        {/* floating brand pill */}
        <div className="fixed inset-x-0 top-5 z-20 flex justify-center">
          <div className="flex h-11 items-center gap-2.5 rounded-full border border-white/10 bg-black/50 px-5 backdrop-blur">
            <img src="/miithii-mark.svg" alt="" className="h-5 w-5 rounded" />
            <span className="text-sm font-semibold tracking-tight">MIITHII</span>
          </div>
        </div>

        <h1 className="mt-16 text-5xl font-semibold leading-[1.08] tracking-[-0.03em] md:text-6xl">
          Support drafts that{" "}
          <span className="text-[#6B84FF]">actually know</span> your product
        </h1>
        <p className="text-muted-foreground mt-5 max-w-xl text-lg">
          Grounded in your docs. Checked by your rules. Sent by you.
        </p>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
          className="mt-9 flex w-full max-w-md items-center gap-2 rounded-full border border-white/10 bg-black/40 p-1.5 backdrop-blur"
        >
          <Input
            type="password"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Workspace key — mii_…"
            autoFocus
            className="h-10 flex-1 border-0 bg-transparent px-4 shadow-none focus-visible:ring-0"
          />
          <Button
            type="submit"
            disabled={busy || !input.trim()}
            className="h-10 rounded-full bg-white px-5 font-medium text-[#0B1120] hover:bg-white/90"
          >
            {busy ? "Checking…" : "Open"}
          </Button>
        </form>
        {error ? <p className="text-destructive mt-3 text-sm">{error}</p> : null}

        {/* the product is the hero */}
        <div className="relative mt-16 w-full">
          <div
            aria-hidden
            className="pointer-events-none absolute -inset-x-8 top-8 bottom-0 rounded-[40px] opacity-40"
            style={{ background: "radial-gradient(ellipse at 50% 80%, #3E63DD 0%, transparent 65%)" }}
          />
          <div className="relative overflow-hidden rounded-xl border border-white/10 shadow-[0_40px_120px_-20px_rgba(0,0,0,0.8)]">
            <img src="/hero-shot.png" alt="MIITHII drafting a refund-policy reply with citations" className="block w-full" />
          </div>
        </div>

        <p className="text-muted-foreground mt-10 text-xs">
          মিথি — to understand. Every draft waits for a person. Nothing sends itself.
        </p>
      </div>
    </div>
  );
}

export function resetKey() {
  localStorage.removeItem(KEY_STORAGE);
  window.location.reload();
}
