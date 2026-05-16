import { createClient, type SupabaseClient } from '@supabase/supabase-js'

let server: SupabaseClient | null = null

// Anonymous server-side client for public reads (no cookies, no session).
// RLS already permits anon reads on poems; this is fine for unauthenticated
// permalink rendering and OG metadata fetching.
export function getSupabaseServer(): SupabaseClient {
  if (!server) {
    server = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      { auth: { persistSession: false, autoRefreshToken: false } },
    )
  }
  return server
}
