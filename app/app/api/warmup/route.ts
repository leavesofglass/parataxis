// Pings the two hot-path Supabase RPCs so PostgREST's function cache + the
// underlying Postgres connections stay warm. recommend_poems will reject with
// "must be authenticated" (the RPC requires auth.uid()) — that's fine, the
// function still gets parsed and its query plan cached before the exception is
// raised, which is the whole point of the ping. get_poems_by_ids has no auth
// check and returns [] for an empty id list.
//
// Public by default so an external uptime service (UptimeRobot, cron-job.org,
// etc.) can hit it every ~5 minutes with a plain GET. The operation is cheap
// and leaks nothing (status codes + elapsed_ms only). If you want to gate
// access, set WARMUP_TOKEN in the env and pass it as either the `token` query
// param (works with free UptimeRobot) or an Authorization: Bearer header.

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  const token = process.env.WARMUP_TOKEN
  if (token) {
    const url = new URL(request.url)
    const provided = url.searchParams.get('token') ??
      request.headers.get('authorization')?.replace(/^Bearer\s+/i, '') ?? ''
    if (provided !== token) {
      return new Response('Unauthorized', { status: 401 })
    }
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!supabaseUrl || !anonKey) {
    return Response.json({ ok: false, reason: 'missing supabase env' }, { status: 500 })
  }

  const headers = {
    apikey: anonKey,
    Authorization: `Bearer ${anonKey}`,
    'Content-Type': 'application/json',
  }

  const t0 = Date.now()
  const [rec, getBy] = await Promise.allSettled([
    fetch(`${supabaseUrl}/rest/v1/rpc/recommend_poems`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ limit_in: 1, corpus_filter: [] }),
    }),
    fetch(`${supabaseUrl}/rest/v1/rpc/get_poems_by_ids`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ poem_ids: [] }),
    }),
  ])

  const summarize = (r: PromiseSettledResult<Response>) =>
    r.status === 'fulfilled' ? { status: r.value.status } : { error: String(r.reason) }

  return Response.json({
    ok: true,
    elapsed_ms: Date.now() - t0,
    recommend_poems: summarize(rec),
    get_poems_by_ids: summarize(getBy),
  })
}
