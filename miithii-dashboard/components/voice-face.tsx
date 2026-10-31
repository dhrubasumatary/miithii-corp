"use client";

import { Mic, Square, X } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { VoiceWaveform } from "@/components/voice-waveform";
import type { VoiceInput } from "@/lib/use-voice-input";

/* The voice face: what the composer's message area becomes while the mic is
   open. One pill, seven states — permission, requesting, opening, denied,
   recording, processing, error — each with its own next action, because a
   recording UI that only shows a red dot leaves every failure unanswerable.

   Escape always backs out (except mid-processing, where the words are already
   on the wire and arriving is better than vanishing). */

function formatClock(ms: number) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function VoiceFace({ voice }: { voice: VoiceInput }) {
  const { status, error, elapsedMs, analyserRef } = voice;

  /* Escape = cancel, but never mid-processing: the request is already on the
     wire and throwing away words that are about to arrive helps nobody. */
  useEffect(() => {
    if (status !== "recording" && status !== "permission" && status !== "error" && status !== "denied") {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        voice.cancel();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [status, voice]);

  if (status === "idle") return null;

  const dismiss = (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label="Cancel voice input"
      onClick={voice.cancel}
      className="text-muted-foreground hover:text-foreground"
    >
      <X className="h-4 w-4" />
    </Button>
  );

  return (
    <div
      className="border-border bg-card/60 flex flex-col items-center justify-center gap-3 rounded-md border border-dashed px-4 py-6"
      role="status"
      aria-live="polite"
    >
      {status === "permission" ? (
        <>
          <button
            type="button"
            onClick={voice.grant}
            className="bg-primary text-primary-foreground hover:bg-primary/90 flex h-14 w-14 items-center justify-center rounded-full transition-transform hover:scale-105 active:scale-95"
            aria-label="Allow microphone access and start dictating"
          >
            <Mic className="h-6 w-6" />
          </button>
          <p className="text-sm font-medium">Dictate with your voice</p>
          <p className="text-muted-foreground text-xs">
            Click the microphone to allow access — the recording stays between
            you and your workspace.
          </p>
          {dismiss}
        </>
      ) : null}

      {status === "requesting" || status === "opening" ? (
        <>
          <div className="bg-primary/15 flex h-14 w-14 items-center justify-center rounded-full">
            <Mic className="text-primary h-6 w-6 animate-pulse" />
          </div>
          <p className="text-muted-foreground text-sm">
            {status === "requesting"
              ? "Waiting for microphone permission…"
              : "Opening microphone…"}
          </p>
        </>
      ) : null}

      {status === "denied" ? (
        <>
          <p className="text-destructive text-sm font-medium">
            {error ?? "Microphone access is blocked."}
          </p>
          <p className="text-muted-foreground text-xs">
            Your browser blocked the mic for this site. Unblock it in the
            address bar&apos;s lock icon → Site settings, then try again.
          </p>
          {dismiss}
        </>
      ) : null}

      {status === "recording" ? (
        <>
          <div className="flex w-full items-center gap-3">
            <span className="relative flex h-3 w-3 shrink-0">
              <span className="bg-destructive absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" />
              <span className="bg-destructive relative inline-flex h-3 w-3 rounded-full" />
            </span>
            <VoiceWaveform analyserRef={analyserRef} />
            <span className="text-muted-foreground w-10 shrink-0 text-right font-mono text-xs tabular-nums">
              {formatClock(elapsedMs)}
            </span>
            <Button size="sm" onClick={voice.stop} className="shrink-0">
              <Square className="h-3.5 w-3.5" />
              Done
            </Button>
            {dismiss}
          </div>
          <p className="text-muted-foreground text-xs">
            Speak the customer&apos;s message — it lands as text when you stop.
            Esc to discard.
          </p>
        </>
      ) : null}

      {status === "processing" ? (
        <>
          <div className="flex w-full items-center gap-3">
            <span className="border-primary border-t-primary-foreground/30 h-4 w-4 shrink-0 animate-spin rounded-full border-2" />
            <VoiceWaveform analyserRef={analyserRef} paused />
            <span className="text-muted-foreground shrink-0 text-sm">
              Transcribing…
            </span>
          </div>
        </>
      ) : null}

      {status === "error" ? (
        <>
          <p className="text-destructive text-sm font-medium">
            {error ?? "Voice input couldn't transcribe that."}
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={voice.start}>
              Try again
            </Button>
            {dismiss}
          </div>
        </>
      ) : null}
    </div>
  );
}
