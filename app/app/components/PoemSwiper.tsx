'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { getSupabase } from '@/lib/supabase'
import type { AuthChangeEvent, Session } from '@supabase/supabase-js'
import { fetchSavedCount } from '@/lib/library'
import type { Poem } from '../types'
import type { Reactions } from './FullPoemView'
import { Masthead } from './Masthead'

// Heavy chunks: framer-motion + FullPoemView (+ sanitize, ShareButton, FlagButton)
// and the signup modal. Neither is needed for first paint — first paint is the
// header + "· · ·" spinner while auth and the first poem batch are in flight.
const PoemCard = dynamic(
  () => import('./PoemCard').then((m) => m.PoemCard),
  { ssr: false, loading: () => null },
)
const SignupNudgeModal = dynamic(
  () => import('./SignupNudgeModal').then((m) => m.SignupNudgeModal),
  { ssr: false, loading: () => null },
)

// Kick off the PoemCard chunk fetch at module parse time, in parallel with the
// initial Supabase auth request. Without this the chunk waits until <PoemCard/>
// mounts (after hydration + auth + first fetch), putting it on the critical
// path and costing ~200ms of time-to-first-poem on slow connections.
if (typeof window !== 'undefined') {
  void import('./PoemCard')
}

// ── Nudge threshold helpers ────────────────────────────────────────────────
const NUDGE_THRESHOLDS = [1, 5, 10] as const
type NudgeThreshold = (typeof NUDGE_THRESHOLDS)[number]
const LS_KEY = 'parataxis_signup_nudge_shown'

function getNextNudgeThreshold(count: number): NudgeThreshold | null {
  try {
    const shown = JSON.parse(localStorage.getItem(LS_KEY) ?? '[]') as number[]
    for (const t of NUDGE_THRESHOLDS) {
      if (count >= t && !shown.includes(t)) return t
    }
  } catch {}
  return null
}

function markNudgeShown(threshold: NudgeThreshold) {
  try {
    const shown = JSON.parse(localStorage.getItem(LS_KEY) ?? '[]') as number[]
    if (!shown.includes(threshold)) {
      localStorage.setItem(LS_KEY, JSON.stringify([...shown, threshold]))
    }
  } catch {}
}

const BATCH = 5
const PREFETCH_AT = 2

const BUCKETS_KEY = 'parataxis_length_buckets'
type LengthBuckets = { short: boolean; medium: boolean; long: boolean }
const DEFAULT_BUCKETS: LengthBuckets = { short: true, medium: true, long: false }

const MIX_MODE_KEY = 'parataxis_mix_mode'

function readMixMode(): number | null {
  if (typeof window === 'undefined') return null
  try {
    const v = localStorage.getItem(MIX_MODE_KEY)
    if (!v) return null
    const parsed = JSON.parse(v)
    if (typeof parsed?.remaining === 'number' && parsed.remaining > 0) return parsed.remaining
  } catch {}
  return null
}

function readBuckets(): LengthBuckets {
  if (typeof window === 'undefined') return DEFAULT_BUCKETS
  try {
    const v = localStorage.getItem(BUCKETS_KEY)
    if (!v) return DEFAULT_BUCKETS
    const parsed = JSON.parse(v)
    if (parsed && typeof parsed === 'object') {
      return {
        short:  parsed.short  !== false,
        medium: parsed.medium !== false,
        long:   parsed.long   !== false,
      }
    }
  } catch {}
  return DEFAULT_BUCKETS
}

const DECK_STATE_KEY = 'parataxis_deck_state'
const DECK_STATE_TTL_MS = 60 * 60 * 1000

interface SavedDeckState {
  poemIds: string[]
  currentIndex: number
  timestamp: number
}

function readSavedDeckState(): SavedDeckState | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(DECK_STATE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<SavedDeckState>
    if (
      typeof parsed?.currentIndex !== 'number' ||
      typeof parsed?.timestamp !== 'number' ||
      !Array.isArray(parsed?.poemIds)
    ) {
      return null
    }
    return parsed as SavedDeckState
  } catch {
    return null
  }
}

function clearSavedDeckState() {
  if (typeof window === 'undefined') return
  try {
    localStorage.removeItem(DECK_STATE_KEY)
  } catch {}
}

export function getPreview(body: string): string {
  const lines = body.split('\n').filter((l) => l.trim() !== '')
  const text = lines.slice(0, 4).join('\n')
  if (text.length <= 240) return text
  return text.slice(0, 240).replace(/\s+\S*$/, '') + '…'
}

const EMPTY_REACTIONS: Reactions = { liked: false, disliked: false, saved: false }

export function PoemSwiper() {
  const fetchingRef = useRef(false)
  const userIdRef = useRef<string | null>(null)
  const isSignedInRef = useRef(false)
  const bucketsRef = useRef<LengthBuckets>(DEFAULT_BUCKETS)
  const mountedRef = useRef(true)
  // Authors of the last ~10 poems added to the deck. Passed to recommend_poems
  // so the server excludes them from the next batch (diversity constraint).
  const recentAuthorsRef = useRef<string[]>([])

  // Lock: prevents double-firing Next while a card is mid-exit.
  const exitingRef = useRef(false)

  const mixRemainingRef = useRef<number | null>(null)

  // Reactions keyed by poem.id — survives Back navigation.
  // useRef for synchronous reads in callbacks; useState counterpart drives renders.
  const reactionsRef = useRef<Record<string, Reactions>>({})
  const [, reactionsTick] = useState(0)

  const getReactions = (poemId: string): Reactions =>
    reactionsRef.current[poemId] ?? EMPTY_REACTIONS

  const setReactions = useCallback((poemId: string, r: Reactions) => {
    reactionsRef.current = { ...reactionsRef.current, [poemId]: r }
    reactionsTick((n) => n + 1)
  }, [])

  const [poems, setPoems] = useState<Poem[]>([])
  const [cardIdx, setCardIdx] = useState(0)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedCount, setSavedCount] = useState(0)
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [nudgeThreshold, setNudgeThreshold] = useState<NudgeThreshold | null>(null)
  const [mixRemaining, setMixRemaining] = useState<number | null>(null)

  // isExiting drives the card's exit animation (Next only).
  const [isExiting, setIsExiting] = useState(false)

  // canBack: true when there are previous poems in the session and no exit in flight.
  const canBack = cardIdx > 0 && !isExiting

  // ── Nudge check on saved count ─────────────────────────────────────────────
  useEffect(() => {
    if (!userEmail && nudgeThreshold === null && savedCount > 0) {
      const threshold = getNextNudgeThreshold(savedCount)
      if (threshold !== null) setNudgeThreshold(threshold)
    }
  }, [savedCount, userEmail, nudgeThreshold])

  // ── Interaction logging ────────────────────────────────────────────────────
  const logInteraction = useCallback((poemId: string, action: string) => {
    const userId = userIdRef.current
    if (!userId) return
    void getSupabase()
      .from('interactions')
      .insert({ user_id: userId, poem_id: poemId, action })
      .then((res: { error: unknown }) => {
        if (res.error) console.error('interaction insert failed:', action, poemId, res.error)
      })
  }, [])

  // ── Poem loading ──────────────────────────────────────────────────────────
  // One path for both anon-auth and signed-in users: the server-side
  // recommend_poems RPC (which routes cold-start callers to its random branch
  // via MIN_SIGNALS). No id list is ever downloaded to the client.
  const loadBatch = useCallback(async (): Promise<{ added: number; detail: string | null }> => {
    if (fetchingRef.current) return { added: 0, detail: null }

    const supabase = getSupabase()
    const buckets = bucketsRef.current

    if (!buckets.short && !buckets.medium && !buckets.long) {
      return { added: 0, detail: 'no-length-filters' }
    }

    // Single gate: cleared in finally so it always resets even if the request throws.
    // Prevents concurrent loads; because there is never more than one in-flight request,
    // out-of-order responses are structurally impossible.
    fetchingRef.current = true
    try {
      const forceRandom = mixRemainingRef.current !== null && mixRemainingRef.current > 0
      const { data, error } = await supabase.rpc('recommend_poems', {
        limit_in:       BATCH,
        show_short:     buckets.short,
        show_medium:    buckets.medium,
        show_long:      buckets.long,
        recent_authors: recentAuthorsRef.current,
        force_random:   forceRandom,
      })
      if (error) {
        const detail = `recommend_poems — ${error.message} (${error.code ?? 'no code'})`
        console.error(detail, error)
        return { added: 0, detail }
      }
      const rows = (data ?? []) as Poem[]
      if (mountedRef.current) {
        setPoems((prev) => {
          const seen = new Set(prev.map((p) => p.id))
          const merged = [...prev, ...rows.filter((p) => !seen.has(p.id))]
          recentAuthorsRef.current = merged.slice(-10).map((p) => p.author)
          return merged
        })
      }
      return { added: rows.length, detail: null }
    } finally {
      fetchingRef.current = false
    }
  }, [])

  // ── Cleanup ───────────────────────────────────────────────────────────────
  useEffect(() => () => { mountedRef.current = false }, [])

  // ── Auth state subscription ───────────────────────────────────────────────
  useEffect(() => {
    const { data: { subscription } } = getSupabase().auth.onAuthStateChange(
      (_event: AuthChangeEvent, session: Session | null) => {
        setUserEmail(session?.user?.email ?? null)
        isSignedInRef.current = session?.user?.is_anonymous === false
      }
    )
    return () => subscription.unsubscribe()
  }, [])

  // ── Init ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    async function init() {
      const t: Record<string, number> = { start: performance.now() }
      const supabase = getSupabase()
      bucketsRef.current = readBuckets()

      const mixR = readMixMode()
      mixRemainingRef.current = mixR
      setMixRemaining(mixR)

      // getSession() reads from localStorage/cookies — no network. Returning
      // users skip the ~200ms /auth/v1/user validation round-trip that getUser()
      // would incur. The SDK auto-refreshes the token in the background if it's
      // near expiry, so a locally-present session is safe to trust for the
      // initial fetch. New users (no session) fall through to signInAnonymously.
      const { data: { session } } = await supabase.auth.getSession()
      const user = session?.user ?? null
      t.afterGetUser = performance.now()
      if (!user) {
        const { data, error: anonError } = await supabase.auth.signInAnonymously()
        t.afterSignIn = performance.now()
        if (anonError) {
          console.error('Auth error:', anonError)
          setError(`Sign-in failed — ${anonError.message}`)
          setReady(true)
          return
        }
        userIdRef.current = data.user?.id ?? null
      } else {
        userIdRef.current = user.id
        setUserEmail(user.email ?? null)
        isSignedInRef.current = user.is_anonymous === false
      }

      const saved = readSavedDeckState()
      const savedIsFresh = saved !== null && Date.now() - saved.timestamp <= DECK_STATE_TTL_MS
      // Signed-in users get a fresh personalised batch on cold load rather
      // than the anon deck they may have been on before signing in.
      if (saved && isSignedInRef.current) clearSavedDeckState()

      let restored = false
      if (saved && !isSignedInRef.current && savedIsFresh && saved.poemIds.length > 0) {
        const { data, error: fetchErr } = await supabase
          .rpc('get_poems_by_ids', { poem_ids: saved.poemIds })
        if (!fetchErr && data) {
          const byId = new Map((data as Poem[]).map((p) => [p.id, p]))
          const ordered = saved.poemIds.map((id) => byId.get(id)).filter(Boolean) as Poem[]
          if (ordered.length > 0) {
            setPoems(ordered)
            setCardIdx(Math.min(saved.currentIndex, ordered.length - 1))
            restored = true
          }
        }
      }

      if (!restored) {
        const result = await loadBatch()
        t.afterLoadBatch = performance.now()
        if (result.detail) setError(result.detail)
      }
      if (userIdRef.current) fetchSavedCount(userIdRef.current).then(setSavedCount)
      t.ready = performance.now()
      ;(window as unknown as { __initTimings?: Record<string, number> }).__initTimings = t
      setReady(true)
    }
    init()
  }, [loadBatch])

  // ── Prefetch ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (ready && poems.length - cardIdx <= PREFETCH_AT) loadBatch()
  }, [cardIdx, poems.length, ready, loadBatch])

  // ── Persist deck state ────────────────────────────────────────────────────
  useEffect(() => {
    if (!ready) return
    if (poems.length === 0) return
    if (cardIdx >= poems.length) { clearSavedDeckState(); return }
    const state: SavedDeckState = {
      poemIds: poems.map((p) => p.id),
      currentIndex: cardIdx,
      timestamp: Date.now(),
    }
    try { localStorage.setItem(DECK_STATE_KEY, JSON.stringify(state)) } catch {}
  }, [poems, cardIdx, ready])

  // ── Reaction handler ──────────────────────────────────────────────────────
  // Toggles like/dislike/save in place; does NOT advance the card.
  // Like and Dislike are mutually exclusive; Save is independent.
  const handleReaction = useCallback((poem: Poem, action: 'like' | 'dislike' | 'save') => {
    const current = getReactions(poem.id)
    const next = { ...current }

    if (action === 'like') {
      next.liked = !current.liked
      if (next.liked && current.disliked) {
        next.disliked = false
        logInteraction(poem.id, 'undislike')
      }
      logInteraction(poem.id, next.liked ? 'like' : 'unlike')
    } else if (action === 'dislike') {
      next.disliked = !current.disliked
      if (next.disliked && current.liked) {
        next.liked = false
        logInteraction(poem.id, 'unlike')
      }
      logInteraction(poem.id, next.disliked ? 'dislike' : 'undislike')
    } else if (action === 'save') {
      next.saved = !current.saved
      logInteraction(poem.id, next.saved ? 'save' : 'unsave')
      setSavedCount((c) => next.saved ? c + 1 : Math.max(0, c - 1))
    }

    setReactions(poem.id, next)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logInteraction, setReactions])

  // ── Next handler ──────────────────────────────────────────────────────────
  // The only action that advances the card. Does not log.
  // Blocked while an exit animation is in flight (exitingRef) and also while
  // we're on the last loaded poem and a batch fetch is in flight — advancing
  // past the end of the array would leave topPoem undefined.
  const handleNext = useCallback((poem: Poem) => {
    if (exitingRef.current) return
    if (cardIdx >= poems.length - 1 && fetchingRef.current) return
    exitingRef.current = true
    // preview_skip is weight-zero in recommend_poems' taste vector — it exists
    // only so the RPC's not-exists dedup excludes swiped-past poems from
    // future batches.
    logInteraction(poem.id, 'preview_skip')
    setIsExiting(true)
  }, [cardIdx, poems.length, logInteraction])

  // Called by PoemCard's onAnimationComplete when the exit animation finishes.
  const handleCardExited = useCallback(() => {
    exitingRef.current = false
    setIsExiting(false)
    setCardIdx((i) => i + 1)
    if (mixRemainingRef.current !== null && mixRemainingRef.current > 0) {
      const next = mixRemainingRef.current - 1
      const nextOrNull = next > 0 ? next : null
      mixRemainingRef.current = nextOrNull
      setMixRemaining(nextOrNull)
      try {
        if (nextOrNull !== null) {
          localStorage.setItem(MIX_MODE_KEY, JSON.stringify({ remaining: nextOrNull }))
        } else {
          localStorage.removeItem(MIX_MODE_KEY)
        }
      } catch {}
    }
  }, [])

  // ── Back handler ─────────────────────────────────────────────────────────
  // Pure navigation — steps back through session history. Never touches DB.
  // Refuses to fire during an in-progress exit: if it cleared exitingRef while
  // an exit animation was running, handleCardExited would later increment cardIdx
  // and undo the backward step.
  const handleBack = useCallback(() => {
    if (exitingRef.current) return
    if (cardIdx === 0) return
    setCardIdx((i) => i - 1)
  }, [cardIdx])

  // ── Share handler ─────────────────────────────────────────────────────────
  const handleShare = useCallback((poem: Poem) => {
    logInteraction(poem.id, 'share')
  }, [logInteraction])

  // ── Render ────────────────────────────────────────────────────────────────
  // Loading shell — uses inline styles so it paints before the CSS <link> in
  // <head> finishes loading. On slow connections that turns the "blank screen
  // for several seconds" into "spinner immediately, then poem." The colour is
  // darker than the app's chrome text so it's actually visible against #ECECEC.
  if (!ready) {
    return (
      <div style={{
        height: '100dvh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: '#ECECEC',
      }}>
        <span style={{
          fontSize: '0.875rem', color: '#9ca3af', letterSpacing: '0.1em',
          fontFamily: 'ui-sans-serif, system-ui, sans-serif',
        }}>·  ·  ·</span>
      </div>
    )
  }

  const topPoem = poems[cardIdx]

  return (
    <main className="relative h-dvh flex flex-col items-center overflow-hidden select-none bg-[#ECECEC]">

      {/* ── Header: sign-in (left) · wordmark (center) · library (right) ── */}
      <div className="w-full flex items-center px-6 pt-3 pb-1 shrink-0 border-b border-[rgba(0,0,0,0.08)]">
        <div className="flex-1 flex items-center h-10">
          <Link
            href="/account"
            className="text-[10px] leading-none font-sans tracking-[0.18em] text-neutral-400 uppercase hover:text-neutral-600 transition-colors max-w-[120px] truncate"
          >
            {userEmail
              ? userEmail.length > 20
                ? 'Account'
                : userEmail
              : 'Sign in'}
          </Link>
        </div>
        <Masthead />
        <div className="flex-1 flex items-center justify-end h-10">
          <Link
            href="/library"
            aria-label="Library"
            className="flex items-center gap-1.5 text-neutral-500 hover:text-neutral-700 transition-colors"
          >
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
              <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
            </svg>
            {savedCount > 0 && (
              <span className="text-[10px] leading-none font-sans tracking-wide tabular-nums text-neutral-400">
                {savedCount}
              </span>
            )}
          </Link>
        </div>
      </div>

      {/* ── Mix mode indicator ── */}
      {mixRemaining !== null && (
        <div className="w-full flex justify-center py-1 shrink-0">
          <span className="font-sans text-[0.65rem] tracking-[0.15em] text-neutral-400 uppercase">
            shuffle · {mixRemaining} left
          </span>
        </div>
      )}

      {/* ── Card area ── */}
      <div className="flex-1 flex items-center justify-center w-full min-h-0 py-4 px-[2.5vw] sm:px-0">
        <div className="relative h-full w-full max-w-[760px]">
          {topPoem ? (
            <PoemCard
              key={topPoem.id}
              poem={topPoem}
              activeReactions={getReactions(topPoem.id)}
              onReaction={(action) => handleReaction(topPoem, action)}
              onNext={() => handleNext(topPoem)}
              onShare={() => handleShare(topPoem)}
              isExiting={isExiting}
              onExited={handleCardExited}
              canBack={canBack}
              onBack={handleBack}
            />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center px-8 text-center gap-3">
              {error === 'no-length-filters' ? (
                <p className="font-sans text-[0.85rem] text-neutral-400 leading-relaxed">
                  No poem lengths selected.{' '}
                  <Link href="/account" className="underline underline-offset-2 hover:text-neutral-600 transition-colors">
                    Go to settings
                  </Link>{' '}
                  and choose at least one.
                </p>
              ) : error ? (
                <>
                  <p className="font-sans text-[0.85rem] text-neutral-400">
                    Couldn&apos;t load poems.
                  </p>
                  <pre className="font-mono text-[0.7rem] text-red-400 text-left bg-white rounded-xl p-3 w-full overflow-auto whitespace-pre-wrap break-all border border-red-100">
                    {error}
                  </pre>
                </>
              ) : (
                <p className="font-sans text-[0.85rem] text-neutral-400">
                  No poems to show right now.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {nudgeThreshold && (
        <SignupNudgeModal
          key={nudgeThreshold}
          threshold={nudgeThreshold}
          onDismiss={() => {
            markNudgeShown(nudgeThreshold)
            setNudgeThreshold(null)
          }}
        />
      )}
    </main>
  )
}
