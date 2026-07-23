'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { AnimatePresence, motion } from 'framer-motion'
import type { TargetAndTransition } from 'framer-motion'
import { getSupabase } from '@/lib/supabase'
import type { AuthChangeEvent, Session } from '@supabase/supabase-js'
import { fetchSavedCount } from '@/lib/library'
import type { Poem } from '../types'
import { FullPoemView } from './FullPoemView'
import type { Reactions } from './FullPoemView'
import { SignupNudgeModal } from './SignupNudgeModal'
import { Masthead } from './Masthead'

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
const DEFAULT_BUCKETS: LengthBuckets = { short: true, medium: true, long: true }

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

// Returns a Supabase query builder with the bucket filter applied.
// Handles all 8 on/off combinations without nested AND-within-OR.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function applyBucketFilter(query: any, b: LengthBuckets): any {
  const { short, medium, long } = b
  if (short && medium && long)   return query
  if (!short && !medium && !long) return query.lte('line_count', 0)
  if (short && medium)            return query.lte('line_count', 40)
  if (medium && long)             return query.gte('line_count', 15)
  if (short && long)              return query.or('line_count.lte.14,line_count.gte.41')
  if (short)                      return query.lte('line_count', 14)
  if (medium)                     return query.gte('line_count', 15).lte('line_count', 40)
  /* long only */                 return query.gte('line_count', 41)
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

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

export function getPreview(body: string): string {
  const lines = body.split('\n').filter((l) => l.trim() !== '')
  const text = lines.slice(0, 4).join('\n')
  if (text.length <= 240) return text
  return text.slice(0, 240).replace(/\s+\S*$/, '') + '…'
}

const EMPTY_REACTIONS: Reactions = { liked: false, disliked: false, saved: false }

// ── PoemCard ──────────────────────────────────────────────────────────────────
// Non-draggable card wrapper. Drives entry and exit animations via the animate
// prop. Entry animation fires only on Back (enterDir='right'); normal forward
// navigation uses initial=false (instant appear). Exit fires when isExiting is
// true (Next only). onExited is guarded by isExiting so it only fires on actual
// exit, not on completion of a Back entry animation.
function PoemCard({
  poem,
  activeReactions,
  onReaction,
  onNext,
  onShare,
  isExiting,
  onExited,
  canBack,
  onBack,
}: {
  poem: Poem
  activeReactions: Reactions
  onReaction: (action: 'like' | 'dislike' | 'save') => void
  onNext: () => void
  onShare: () => void
  isExiting: boolean
  onExited: () => void
  canBack: boolean
  onBack: () => void
}) {
  const exitTarget: TargetAndTransition = isExiting
    ? { x: '160%', opacity: 0 }
    : { x: 0, y: 0, opacity: 1 }

  return (
    <motion.div
      className="absolute inset-0"
      style={{ zIndex: 2 }}
      initial={false}
      animate={exitTarget}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      onAnimationComplete={() => { if (isExiting) onExited() }}
    >
      <FullPoemView
        poem={poem}
        activeReactions={activeReactions}
        onReaction={onReaction}
        onNext={onNext}
        onShare={onShare}
        onClose={() => {}}
        asCard
        canBack={canBack}
        onBack={onBack}
      />
    </motion.div>
  )
}

export function PoemSwiper() {
  const poolRef = useRef<string[]>([])
  const poolPosRef = useRef(0)
  const fetchingRef = useRef(false)
  const userIdRef = useRef<string | null>(null)
  const isSignedInRef = useRef(false)
  const bucketsRef = useRef<LengthBuckets>(DEFAULT_BUCKETS)

  // Lock: prevents double-firing Next while a card is mid-exit.
  const exitingRef = useRef(false)

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
  const loadBatch = useCallback(async () => {
    if (fetchingRef.current) return

    const supabase = getSupabase()
    const uid = userIdRef.current
    const buckets = bucketsRef.current

    if (isSignedInRef.current && uid) {
      fetchingRef.current = true
      const { data, error } = await supabase.rpc('recommend_poems', {
        user_id_in:  uid,
        limit_in:    BATCH,
        show_short:  buckets.short,
        show_medium: buckets.medium,
        show_long:   buckets.long,
      })
      fetchingRef.current = false
      if (error || !data) {
        console.error('recommend_poems error:', error)
        return
      }
      setPoems((prev) => {
        const seen = new Set(prev.map((p) => p.id))
        const fresh = (data as Poem[]).filter((p) => !seen.has(p.id))
        return [...prev, ...fresh]
      })
      return
    }

    if (poolRef.current.length === 0) return
    fetchingRef.current = true

    if (poolPosRef.current >= poolRef.current.length) {
      poolRef.current = shuffle(poolRef.current)
      poolPosRef.current = 0
    }

    const batch = poolRef.current.slice(poolPosRef.current, poolPosRef.current + BATCH)
    poolPosRef.current += batch.length

    let query = supabase
      .from('poems')
      .select('id, title, author, body, line_count')
      .in('id', batch)
    query = applyBucketFilter(query, buckets)
    const { data, error } = await query

    fetchingRef.current = false

    if (error || !data) {
      console.error('Fetch error:', error)
      return
    }

    const ordered = batch
      .map((id) => data.find((p: Poem) => p.id === id))
      .filter(Boolean) as Poem[]

    setPoems((prev) => [...prev, ...ordered])
  }, [])

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
      const supabase = getSupabase()
      bucketsRef.current = readBuckets()

      const { data: { user } } = await supabase.auth.getUser()
      if (!user) {
        const { data, error } = await supabase.auth.signInAnonymously()
        if (error) console.error('Auth error:', error)
        else { userIdRef.current = data.user?.id ?? null }
      } else {
        userIdRef.current = user.id
        setUserEmail(user.email ?? null)
        isSignedInRef.current = user.is_anonymous === false
      }

      const saved = readSavedDeckState()
      const savedIsFresh = saved !== null && Date.now() - saved.timestamp <= DECK_STATE_TTL_MS
      if (saved && isSignedInRef.current) clearSavedDeckState()

      if (!isSignedInRef.current) {
        let idQuery = supabase.from('poems').select('id')
        idQuery = applyBucketFilter(idQuery, bucketsRef.current)
        const { data: idRows, error: idError } = await idQuery

        if (idError || !idRows) {
          console.error('poems select failed:', JSON.stringify(idError))
          setError(`Could not load poems. (${idError?.code ?? 'unknown'}: ${idError?.message ?? 'no data'})`)
          return
        }

        poolRef.current = shuffle(idRows.map((r: { id: string }) => r.id))
        poolPosRef.current = 0
      }

      let restored = false
      if (saved && !isSignedInRef.current && savedIsFresh && saved.poemIds.length > 0) {
        const { data, error: fetchErr } = await supabase
          .from('poems')
          .select('id, title, author, body, line_count')
          .in('id', saved.poemIds)
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

      if (!restored) await loadBatch()
      if (userIdRef.current) fetchSavedCount(userIdRef.current).then(setSavedCount)
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
  const handleNext = useCallback((poem: Poem) => {
    if (exitingRef.current) return
    exitingRef.current = true
    void poem  // captured for potential future logging
    setIsExiting(true)
  }, [])

  // Called by PoemCard's onAnimationComplete when the exit animation finishes.
  const handleCardExited = useCallback(() => {
    exitingRef.current = false
    setIsExiting(false)
    setCardIdx((i) => i + 1)
  }, [])

  // ── Back handler ─────────────────────────────────────────────────────────
  // Pure navigation — steps back through session history. Never touches DB.
  const handleBack = useCallback(() => {
    if (cardIdx === 0) return
    exitingRef.current = false
    setIsExiting(false)
    setCardIdx((i) => i - 1)
  }, [cardIdx])

  // ── Share handler ─────────────────────────────────────────────────────────
  const handleShare = useCallback((poem: Poem) => {
    logInteraction(poem.id, 'share')
  }, [logInteraction])

  // ── Render ────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="h-dvh flex items-center justify-center bg-[#ECECEC]">
        <p className="text-sm font-sans text-neutral-400">{error}</p>
      </div>
    )
  }

  if (!ready) {
    return (
      <div className="h-dvh flex items-center justify-center bg-[#ECECEC]">
        <span className="text-sm font-sans text-neutral-300 tracking-widest">·  ·  ·</span>
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
            className="text-[10px] leading-none font-sans tracking-[0.18em] text-neutral-300 uppercase hover:text-neutral-500 transition-colors max-w-[120px] truncate"
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

      {/* ── Card area ── */}
      <div className="flex-1 flex items-center justify-center w-full min-h-0 py-4 px-[2.5vw] sm:px-0">
        <div className="relative h-full w-full max-w-[760px]">
          {topPoem && (
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
          )}
        </div>
      </div>

      <AnimatePresence>
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
      </AnimatePresence>
    </main>
  )
}
