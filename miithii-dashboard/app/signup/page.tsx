"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KEY_STORAGE, ENGINE_URL } from "@/lib/engine";

export default function SignupPage() {
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState(""); // honeypot — humans never see this
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mintedKey, setMintedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const router = useRouter();

  async function submit() {
    if (!company.trim() || !email.trim()) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`${ENGINE_URL}/v1/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company: company.trim(), email: email.trim(), website }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        api_key?: string;
        detail?: string;
      };
      if (!res.ok || !data.api_key) {
        throw new Error(data.detail ?? "Signup failed");
      }
      setMintedKey(data.api_key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setBusy(false);
    }
  }

  function enter() {
    if (!mintedKey) return;
    localStorage.setItem(KEY_STORAGE, mintedKey);
    router.push("/tickets");
  }

  async function copyKey() {
    if (!mintedKey) return;
    await navigator.clipboard.writeText(mintedKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (mintedKey) {
    return (
      <div className="flex min-h-svh items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Your workspace is ready</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-muted-foreground text-sm">
              This key is shown once. It is the only credential for your
              workspace, so copy it somewhere safe.
            </p>
            <div className="rounded-lg border bg-muted/40 p-3 font-mono text-sm break-all">
              {mintedKey}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => void copyKey()}>
                {copied ? "Copied" : "Copy key"}
              </Button>
              <Button className="flex-1" onClick={enter}>
                Enter MIITHII
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="mb-7 flex flex-col items-center gap-3 text-center">
          <img src="/miithii-mark.svg" alt="MIITHII" className="h-12 w-12 rounded-xl" />
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Create your workspace</h1>
            <p className="text-muted-foreground text-sm">
              One workspace per email. You get your key the moment it is created.
            </p>
          </div>
        </div>
        <Card>
          <CardContent className="flex flex-col gap-4 pt-6">
            <div className="flex flex-col gap-2">
              <Label htmlFor="su-company">Company</Label>
              <Input
                id="su-company"
                value={company}
                onChange={(event) => setCompany(event.target.value)}
                placeholder="Acme Inc"
                maxLength={100}
                disabled={busy}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="su-email">Your email</Label>
              <Input
                id="su-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@company.com"
                disabled={busy}
              />
            </div>
            {/* honeypot */}
            <input
              type="text"
              name="website"
              value={website}
              onChange={(event) => setWebsite(event.target.value)}
              tabIndex={-1}
              autoComplete="off"
              className="hidden"
              aria-hidden="true"
            />
            {error ? <p className="text-destructive text-sm">{error}</p> : null}
            <Button onClick={() => void submit()} disabled={busy || !company.trim() || !email.trim()}>
              {busy ? "Provisioning…" : "Create workspace"}
            </Button>
            <p className="text-muted-foreground text-center text-xs">
              Every draft waits for a person. Teammates sign in with their own email, never a shared key.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
