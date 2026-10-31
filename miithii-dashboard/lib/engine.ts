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
  const res = await fetch(`${ENGINE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": getApiKey(),
      ...(init?.headers ?? {}),
    },
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

export const engine = {
  async verifyKey(key: string): Promise<boolean> {
    const res = await fetch(`${ENGINE_URL}/v1/tickets`, {
      headers: { "X-API-Key": key },
      cache: "no-store",
    });
    return res.ok;
  },
  listTickets: () => req<TicketRow[]>("/v1/tickets"),
  createTicket: (subject: string, body: string) =>
    req<AnalysisResult>("/v1/tickets", {
      method: "POST",
      body: JSON.stringify({ subject, body }),
    }),
  analyses: (ticketId: string) =>
    req<AnalysisRow[]>(`/v1/tickets/${ticketId}/analyses`),
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
