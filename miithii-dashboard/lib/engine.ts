import { getSupabase } from "./supabase";

export type AnalysisResult = {
  ticket_id: string;
  category: string;
  severity: string;
  difficulty: string;
  action: string;
  answer: string | null;
  requires_human: boolean;
  policy_flags: string[];
  citations: string[];
  confidence: number | null;
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  cost_usd: number | null;
};

export type TicketRow = {
  id: string;
  subject: string;
  status: string;
  created_at: string;
};

export type AnalysisRow = {
  id: string;
  action: string;
  category: string;
  answer: string | null;
  policy_flags: string[];
  confidence: number | null;
  latency_ms: number | null;
  provider: string | null;
  model: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  cost_usd: number | null;
  created_at: string;
};

export type KnowledgeRow = {
  id: string;
  title: string;
  kind: string;
  status: string;
  origin_url: string | null;
  chunks: number;
  created_at: string;
};

export type TeamMember = {
  id: string;
  email: string;
  name: string | null;
  role: string;
  joined: string;
};

export type TranscriptionResult = {
  text: string;
  language_code: string | null;
  request_id?: string;
};

export class EngineError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const ENGINE_URL =
  process.env.NEXT_PUBLIC_ENGINE_URL ?? "http://localhost:8000";
export const KEY_STORAGE = "mii_api_key";

export function getApiKey(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(KEY_STORAGE) ?? "";
}

function handleAuthFailure() {
  // the key stopped working — drop it and let the gate take over
  localStorage.removeItem(KEY_STORAGE);
  window.location.reload();
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  // named human (Supabase session) beats the shared workspace key
  const supabase = getSupabase();
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session) {
      headers["Authorization"] = `Bearer ${data.session.access_token}`;
    }
  }
  if (!headers["Authorization"]) {
    headers["X-API-Key"] = getApiKey();
  }
  const res = await fetch(`${ENGINE_URL}${path}`, {
    ...init,
    headers: { ...headers, ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (res.status === 401) {
    handleAuthFailure();
    throw new EngineError(401, "Invalid or missing API key");
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new EngineError(res.status, body.detail ?? `Engine error ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type UsageDay = {
  day: string;
  events: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
};

export type UsageSummary = {
  days: UsageDay[];
  totals: { events: number; prompt_tokens: number; completion_tokens: number; cost_usd: number };
};

export const engine = {
  async verifyKey(key: string): Promise<boolean> {
    const res = await fetch(`${ENGINE_URL}/v1/tickets`, {
      headers: { "X-API-Key": key },
      cache: "no-store",
    });
    return res.ok;
  },
  usage: () => req<UsageSummary>("/v1/usage"),
  listUsers: () => req<TeamMember[]>("/v1/users"),
  inviteUser: (email: string) =>
    req<TeamMember>("/v1/users", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  async signup(company: string, email: string): Promise<{ tenant_id: string; api_key: string }> {
    const res = await fetch(`${ENGINE_URL}/v1/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company, email }),
    });
    const data = (await res.json().catch(() => ({}))) as {
      api_key?: string;
      detail?: string;
    };
    if (!res.ok || !data.api_key) throw new Error(data.detail ?? "Signup failed");
    return { tenant_id: "", api_key: data.api_key };
  },
  listTickets: () => req<TicketRow[]>("/v1/tickets"),
  /**
   * Streams the real pipeline stages over SSE (classify -> retrieve ->
   * policy -> draft) and resolves with the final analysis.
   */
  async createTicketStream(
    subject: string,
    body: string,
    onStage?: (stage: string) => void,
  ): Promise<AnalysisResult> {
    const res = await fetch(`${ENGINE_URL}/v1/tickets/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "X-API-Key": getApiKey(),
      },
      body: JSON.stringify({ subject, body }),
    });
    if (res.status === 401) {
      handleAuthFailure();
      throw new EngineError(401, "Invalid or missing API key");
    }
    if (!res.ok || !res.body) {
      throw new EngineError(res.status, `Engine error ${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let result: AnalysisResult | null = null;

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        let event = "message";
        let data = "";
        for (const line of raw.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;
        const parsed = JSON.parse(data) as { stage?: string; detail?: string };
        if (event === "progress" && parsed.stage) onStage?.(parsed.stage);
        else if (event === "result") result = parsed as unknown as AnalysisResult;
        else if (event === "error")
          throw new EngineError(500, parsed.detail ?? "Stream failed");
      }
    }
    if (!result) throw new EngineError(500, "Stream ended without a result");
    return result;
  },
  createTicket: (subject: string, body: string) =>
    req<AnalysisResult>("/v1/tickets", {
      method: "POST",
      body: JSON.stringify({ subject, body }),
    }),
  analyses: (ticketId: string) =>
    req<AnalysisRow[]>(`/v1/tickets/${ticketId}/analyses`),
  /**
   * Dictation: the raw recording IS the request body — no multipart, no
   * storage engine-side. Content-Type tells the engine which container the
   * browser wrote so the filename it hands the provider stays honest.
   */
  async transcribe(clip: Blob, mimeType: string): Promise<TranscriptionResult> {
    const headers: Record<string, string> = {
      "Content-Type": mimeType || "application/octet-stream",
    };
    const supabase = getSupabase();
    if (supabase) {
      const { data } = await supabase.auth.getSession();
      if (data.session) {
        headers["Authorization"] = `Bearer ${data.session.access_token}`;
      }
    }
    if (!headers["Authorization"]) {
      headers["X-API-Key"] = getApiKey();
    }
    const res = await fetch(`${ENGINE_URL}/v1/transcribe`, {
      method: "POST",
      headers,
      body: clip,
      cache: "no-store",
    });
    if (res.status === 401) {
      handleAuthFailure();
      throw new EngineError(401, "Invalid or missing API key");
    }
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { detail?: string };
      throw new EngineError(res.status, body.detail ?? `Engine error ${res.status}`);
    }
    return res.json() as Promise<TranscriptionResult>;
  },
  listKnowledge: () => req<KnowledgeRow[]>("/v1/knowledge"),
  uploadKnowledge: (title: string, content: string) =>
    req<{ source_id: string; status: string; error: string | null }>(
      "/v1/knowledge/upload",
      { method: "POST", body: JSON.stringify({ title, content }) },
    ),
  crawlKnowledge: (url: string, maxPages: number) =>
    req<{ ingested: { source_id: string; title: string; status: string }[] }>(
      "/v1/knowledge/crawl",
      { method: "POST", body: JSON.stringify({ url, max_pages: maxPages }) },
    ),
};
