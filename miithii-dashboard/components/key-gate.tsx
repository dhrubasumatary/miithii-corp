"use client";

import { BookOpen, Check, FileText, KeyRound, Mail, Receipt, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { motion } from "motion/react";
import { useEffect, useState } from "react";

import { FadeUp } from "@/components/motion";
import { HeroDemo } from "@/components/hero-demo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ENGINE_URL, KEY_STORAGE, engine, getApiKey } from "@/lib/engine";
import { getSupabase } from "@/lib/supabase";

const EASE = [0.22, 1, 0.36, 1] as const;

export function KeyGate({ children }: { children: React.ReactNode }) {
  const [key, setKey] = useState<string | null>(null);
  const [signedIn, setSignedIn] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState<"email" | "key">("email");
  const [email, setEmail] = useState("");
  const [magicSent, setMagicSent] = useState(false);
  const [otp, setOtp] = useState("");
  const [keyInput, setKeyInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const supabase = getSupabase();
    if (supabase) {
      void supabase.auth
        .getSession()
        .then(({ data }) => {
          if (data.session) setSignedIn(data.session.access_token);
          // No session ≠ no identity: a returning workspace-key user's
          // credential is still in localStorage, and the gate must honor
          // it — signup hands every new tenant a key, and ignoring the
          // stored one locks them out on their second visit.
          else setKey(getApiKey());
          setReady(true);
        })
        .catch(() => {
          // auth server unreachable — the stored key is still worth trying;
          // a bad one gets thrown out by the engine's own 401 path
          setKey(getApiKey());
          setReady(true);
        });
      const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
        if (event === "SIGNED_IN" && session) {
          setSignedIn(session.access_token);
          window.location.reload();
        }
      });
      return () => sub.subscription.unsubscribe();
    }
    setKey(getApiKey());
    setReady(true);
    return undefined;
  }, []);

  if (!ready) return null;
  if (key || signedIn) return <>{children}</>;

  const hasSupabase = getSupabase() !== null;
  const emailMode = mode === "email" && hasSupabase;

  async function sendMagicLink() {
    const supabase = getSupabase();
    if (!supabase || !email.trim()) return;
    setBusy(true);
    setError("");
    const { error: err } = await supabase.auth.signInWithOtp({ email: email.trim() });
    setBusy(false);
    if (err) setError(err.message);
    else setMagicSent(true);
  }

  async function verifyOtp() {
    const supabase = getSupabase();
    if (!supabase || otp.trim().length < 6) return;
    setBusy(true);
    setError("");
    const { error: err } = await supabase.auth.verifyOtp({
      email: email.trim(),
      token: otp.trim(),
      type: "email",
    });
    setBusy(false);
    if (err) setError(err.message);
    // onAuthStateChange handles the session + reload
  }

  async function saveKey() {
    if (!keyInput.trim()) return;
    setBusy(true);
    setError("");
    try {
      const ok = await engine.verifyKey(keyInput.trim());
      if (!ok) throw new Error("That key didn't work");
      localStorage.setItem(KEY_STORAGE, keyInput.trim());
      setKey(keyInput.trim());
    } catch (err) {
      // "Failed to fetch" is ours to interpret, theirs to read — network
      // trouble gets a sentence with a way forward, not a stack overflow
      const raw = err instanceof Error ? err.message : "Verification failed";
      setError(
        /fetch|network|timed out/i.test(raw)
          ? "Couldn't reach MIITHII — check your connection and try again."
          : raw,
      );
    } finally {
      setBusy(false);
    }
  }

  function authPanel() {
    if (magicSent) {
      return (
        <div className="bg-card mx-auto max-w-md rounded-2xl border p-6">
          <p className="flex items-center justify-center gap-2 font-medium">
            <Mail className="text-primary h-4 w-4" />
            Check your inbox
          </p>
          <p className="text-muted-foreground mt-2 text-sm">
            We sent a sign-in link to {email}. Open it on this device.
          </p>
        </div>
      );
    }
    return emailMode ? (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void sendMagicLink();
        }}
        className="mx-auto flex w-full max-w-md items-center gap-2 rounded-full border border-white/10 bg-black/40 p-1.5 backdrop-blur"
      >
        <Input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@company.com"
          className="h-10 flex-1 border-0 bg-transparent px-4 shadow-none focus-visible:ring-0"
        />
        <Button
          type="submit"
          disabled={busy || !email.trim()}
          className="h-10 rounded-full bg-white px-5 font-medium text-[#181818] hover:bg-white/90"
        >
          {busy ? "Sending…" : "Sign in"}
        </Button>
      </form>
    ) : (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void saveKey();
        }}
        className="mx-auto flex w-full max-w-md items-center gap-2 rounded-full border border-white/10 bg-black/40 p-1.5 backdrop-blur"
      >
        <Input
          type="password"
          value={keyInput}
          onChange={(event) => setKeyInput(event.target.value)}
          placeholder="Workspace key — mii_…"
          className="h-10 flex-1 border-0 bg-transparent px-4 shadow-none focus-visible:ring-0"
        />
        <Button
          type="submit"
          disabled={busy || !keyInput.trim()}
          className="h-10 rounded-full bg-white px-5 font-medium text-[#181818] hover:bg-white/90"
        >
          {busy ? "Checking…" : "Open"}
        </Button>
      </form>
    );
  }

  function authToggle() {
    return hasSupabase ? (
      <button
        type="button"
        onClick={() => setMode(mode === "email" ? "key" : "email")}
        className="text-muted-foreground inline-flex items-center gap-1.5 text-xs hover:text-foreground"
      >
        {mode === "email" ? (
          <>
            <KeyRound className="h-3.5 w-3.5" />
            Use a workspace key instead
          </>
        ) : (
          <>
            <Mail className="h-3.5 w-3.5" />
            Sign in with work email
          </>
        )}
      </button>
    ) : null;
  }

  return (
    <div className="relative min-h-svh overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -10%, rgb(99 91 255 / 0.16), transparent), radial-gradient(ellipse 60% 40% at 50% 110%, rgb(99 91 255 / 0.10), transparent), #141414",
        }}
      />

      <div className="relative mx-auto max-w-4xl px-6">
        <div className="fixed inset-x-0 top-5 z-20 flex justify-center">
          <div className="flex h-11 items-center gap-2.5 rounded-full border border-white/10 bg-black/50 px-5 backdrop-blur">
            <img src="/miithii-mark.svg" alt="" className="h-5 w-5 rounded" />
            <span className="text-sm font-semibold tracking-tight">MIITHII</span>
          </div>
        </div>

        <div className="flex flex-col items-center pt-32 text-center">
          <h1 className="text-5xl font-semibold leading-[1.08] tracking-[-0.03em] md:text-6xl">
            Support drafts that{" "}
            <span className="text-primary">actually know</span> your product
          </h1>
          <p className="text-muted-foreground mt-5 max-w-xl text-lg">
            Grounded in your docs. Checked by your rules. Sent by you.
          </p>
          <div className="mt-9 w-full">{authPanel()}</div>
          {error ? <p className="text-destructive mt-3 text-sm">{error}</p> : null}
          <div className="mt-4">{authToggle()}</div>
          <p className="mt-4 text-sm">
            <Link href="/signup" className="text-primary hover:underline">
              No key? Create your workspace →
            </Link>
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2, ease: EASE }}
          className="relative mt-16 w-full"
        >
          <div
            aria-hidden
            className="pointer-events-none absolute -inset-x-10 top-10 bottom-0 rounded-[40px] opacity-40"
            style={{ background: "radial-gradient(ellipse at 50% 80%, rgb(139 133 255) 0%, transparent 65%)" }}
          />
          <div className="relative overflow-hidden rounded-xl border border-white/10 shadow-[0_40px_120px_-20px_rgba(0,0,0,0.8)]">
            <HeroDemo />
          </div>
        </motion.div>

        <FadeUp className="mt-32">
          <h2 className="text-center text-3xl font-semibold tracking-tight">
            Grounded in your docs.
          </h2>
          <p className="text-muted-foreground mx-auto mt-3 max-w-lg text-center">
            Every draft carries its sources. If the answer isn&apos;t in your
            documents, the draft says so instead of guessing.
          </p>
          <div
            className="raised mx-auto mt-10 max-w-xl overflow-hidden rounded-2xl border border-border bg-card p-6"
          >
            <div className="flex items-center gap-2 text-sm font-medium">
              <BookOpen className="h-4 w-4 text-primary" />
              Knowledge
              <span className="text-muted-foreground ml-auto text-xs">48 articles</span>
            </div>
            <div className="mt-4 flex flex-col gap-2 text-sm">
              {["billing.md", "refund-policy.md", "pricing.md"].map((doc) => (
                <div key={doc} className="flex items-center gap-2.5 rounded-lg bg-white/5 px-3 py-2">
                  <FileText className="text-muted-foreground h-4 w-4" />
                  {doc}
                  <Check className="ml-auto h-4 w-4 text-emerald-400" />
                </div>
              ))}
            </div>
            <div className="mt-5 flex flex-wrap gap-1.5">
              {["billing.md (part 1)", "pricing.md (part 2)", "refund-policy.md (part 1)"].map((c) => (
                <span key={c} className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-foreground">
                  {c}
                </span>
              ))}
            </div>
          </div>
        </FadeUp>

        <FadeUp className="mt-32">
          <h2 className="text-center text-3xl font-semibold tracking-tight">
            Checked by your rules.
          </h2>
          <p className="text-muted-foreground mx-auto mt-3 max-w-lg text-center">
            Policy is code, not a suggestion. Exceptions are refused, routed to
            a human, and the draft says exactly that.
          </p>
          <div
            className="raised mx-auto mt-10 max-w-xl rounded-2xl border border-border bg-card p-6"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Refund outside the 30-day window</span>
              <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400">
                human review
              </span>
            </div>
            <div className="mt-3">
              <span className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-xs text-red-400">
                refund exception
              </span>
            </div>
            <p className="mt-4 text-sm leading-relaxed text-foreground-soft">
              &quot;Under our standard refund policy, refund eligibility is within 14
              days for monthly plans or 30 days for annual plans. Because your
              purchase is beyond this standard window, this request requires
              review by our billing team.&quot;
            </p>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {["billing.md (part 1)", "refund-policy.md (part 1)"].map((c) => (
                <span key={c} className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-muted-foreground">
                  {c}
                </span>
              ))}
            </div>
            <p className="mt-4 flex items-center gap-1.5 text-xs text-amber-400/80">
              <ShieldCheck className="h-3.5 w-3.5" />
              Needs a human read before this goes out.
            </p>
          </div>
        </FadeUp>

        <FadeUp className="mt-32">
          <h2 className="text-center text-3xl font-semibold tracking-tight">
            Nothing hides.
          </h2>
          <p className="text-muted-foreground mx-auto mt-3 max-w-lg text-center">
            Every analysis is a receipt: the action taken, the policy flags, the
            tokens spent, the measured cost. Yours to inspect, forever.
          </p>
          <div
            className="raised mx-auto mt-10 max-w-xl overflow-hidden rounded-2xl border border-border bg-card"
          >
            <div className="flex items-center gap-2 border-b border-white/5 px-6 py-4 text-sm font-medium">
              <Receipt className="h-4 w-4 text-emerald-400" />
              Receipt — ignore everything
              <span className="text-muted-foreground ml-auto text-xs">just now</span>
            </div>
            <div className="flex flex-col gap-3 p-6 text-sm">
              <div className="flex items-center gap-2">
                <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400">refuse</span>
                <span className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-xs text-red-400">prompt injection</span>
              </div>
              <p className="text-foreground">
                &quot;I cannot comply with this request. I am unable to reveal
                internal system instructions or disclose account API keys.&quot;
              </p>
              <div className="text-muted-foreground grid grid-cols-3 gap-2 text-xs">
                <div><span className="text-emerald-400/80">9.8s</span> latency</div>
                <div><span className="text-emerald-400/80">1,378</span> tokens</div>
                <div><span className="text-emerald-400/80">$0.0021</span> cost</div>
              </div>
            </div>
          </div>
        </FadeUp>

        <FadeUp className="mt-32">
          <div className="grid gap-4 text-center sm:grid-cols-3">
            {[
              ["95%", "retrieval hit@3 on our golden set"],
              ["~$0.002", "measured cost per draft"],
              ["<15s", "typical draft, end to end"],
            ].map(([big, small]) => (
              <div key={big} className="rounded-2xl border border-white/5 bg-white/[0.02] p-6">
                <p className="text-2xl font-semibold text-primary">{big}</p>
                <p className="text-muted-foreground mt-1 text-xs">{small}</p>
              </div>
            ))}
          </div>
        </FadeUp>

        <FadeUp className="mt-32">
          <h2 className="text-center text-3xl font-semibold tracking-tight">Pricing</h2>
          <p className="text-muted-foreground mx-auto mt-3 max-w-lg text-center">
            Early access is free while we learn from the first teams. Billing
            comes with the boring parts: invoices, SLAs, and a signed DPA.
          </p>
          <div className="mx-auto mt-10 grid max-w-2xl gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-primary/40 bg-primary/10 p-6 text-left">
              <p className="text-sm font-medium text-foreground">Early access</p>
              <p className="mt-2 text-3xl font-semibold">
                $0<span className="text-muted-foreground text-base font-normal"> / month</span>
              </p>
              <ul className="text-muted-foreground mt-4 flex flex-col gap-2 text-sm">
                <li>Your own workspace + named seats</li>
                <li>Docs by upload or help-center crawl</li>
                <li>Citations, policy checks, full audit trail</li>
              </ul>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6 text-left">
              <p className="text-muted-foreground text-sm font-medium">With billing</p>
              <p className="mt-2 text-3xl font-semibold">
                Per seat<span className="text-muted-foreground text-base font-normal"> / month</span>
              </p>
              <ul className="text-muted-foreground mt-4 flex flex-col gap-2 text-sm">
                <li>Everything in early access, unlimited</li>
                <li>Priority region + custom domain</li>
                <li>Invoices, SLA, signed DPA</li>
              </ul>
            </div>
          </div>
          <p className="text-muted-foreground mt-6 text-center text-sm">
            Questions, or want in?{" "}
            <a
              href="https://github.com/dhrubasumatary/miithii-corp"
              className="text-primary hover:underline"
            >
              github.com/dhrubasumatary/miithii-corp
            </a>
          </p>
        </FadeUp>

        <FadeUp className="mt-32 mb-16 flex flex-col items-center gap-6 text-center">
          <h2 className="text-3xl font-semibold tracking-tight">
            Ready for drafts that wait for a person?
          </h2>
          <div className="w-full">{authPanel()}</div>
          <div>{authToggle()}</div>
          <p className="mt-2 text-sm">
            <Link href="/signup" className="text-primary hover:underline">
              No key? Create your workspace →
            </Link>
          </p>
          <p className="text-muted-foreground text-xs">
            মিথি — to understand. Every draft waits for a person. Nothing sends itself.
          </p>
        </FadeUp>
      </div>
    </div>
  );
}

export function resetKey() {
  localStorage.removeItem(KEY_STORAGE);
  window.location.reload();
}
