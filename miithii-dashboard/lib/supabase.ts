import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

let client: SupabaseClient | null = null;

/** Null when Supabase isn't configured — the key-gate falls back to API keys. */
export function getSupabase(): SupabaseClient | null {
  if (!URL || !ANON) return null;
  if (!client) client = createClient(URL, ANON);
  return client;
}
