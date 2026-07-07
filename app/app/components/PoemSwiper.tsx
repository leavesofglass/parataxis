'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { AnimatePresence } from 'framer-motion'
import { getSupabase } from '@/lib/supabase'
import type { AuthChangeEvent, Session } from '@supabase/supabase-js'
import { fetchSavedCount } from '@/lib/library'
import type { Poem } from '../types'
import { SwipeCard } from './SwipeCard'
import { FullPoemView } from './FullPoemView'
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

const LINE_MAX_KEY = 'parataxis_line_max'

function readLineMax(): number | null {
  if (typeof window === 'undefined') return null
  try {
    const v = localStorage.getItem(LINE_MAX_KEY)
    if (!v) return null
    const n = Number(v)
    return Number.isFinite(n) && n > 0 ? n : null
  } catch {
    return null
  }
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

type FullPoemAction = 'skip' | 'save' | 'super_like'

export function PoemSwiper() {
  const poolRef = useRef<string[]>([])
  const poolPosRef = useRef(0)
  const fetchingRef = useRef(false)
  const userIdRef = useRef<string | null>(null)
  const isSignedInRef = useRef(false)
  const lineMaxRef = useRef<number | null>(null)

  const [poems, setPoems] = useState<Poem[]>([])
  const [cardIdx, setCardIdx] = useState(0)
  const [openPoem, setOpenPoem] = useState<Poem | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedCount, setSavedCount] = useState(0)
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [nudgeThreshold, setNudgeThreshold] = useState<NudgeThreshold | null>(null)

  // ── Interaction logging ────────────────────────────────────────────────────
  // Fire-and-forget: never blocks the UI, never surfaces errors to the user.
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
    const lineMax = lineMaxRef.current

    // Signed-in: recommend_poems returns the next batch ranked against the
    // user's current taste vector. Dedup against poems already in the deck —
    // until the user interacts with the tail of the current batch, those
    // poems remain candidates and can come back in a prefetched batch.
    if (isSignedInRef.current && uid) {
      fetchingRef.current = true
      const { data, error } = await supabase.rpc('recommend_poems', {
        user_id_in: uid,
        limit_in: BATCH,
        line_max_in: lineMax,
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

    // Anon: random shuffled pool of all poem IDs.
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
    if (lineMax !== null) query = query.lte('line_count', lineMax)
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

  // ── Auth state subscription — keeps email label in sync ──────────────────
  // onAuthStateChange fires INITIAL_SESSION immediately on subscribe (with the
  // current live session), then SIGNED_IN / TOKEN_REFRESHED on changes.
  // This is more reliable than reading email from the decoded JWT in getSession()
  // which can be stale if the token was issued before the email was attached.
  useEffect(() => {
    const { data: { subscription } } = getSupabase().auth.onAuthStateChange(
      (_event: AuthChangeEvent, session: Session | null) => {
        setUserEmail(session?.user?.email ?? null)
        isSignedInRef.current = session?.user?.is_anonymous === false
      }
    )
    return () => subscription.unsubscribe()
  }, [])

  // ── Init: anon auth + fetch all IDs + first batch ─────────────────────────
  useEffect(() => {
    async function init() {
      const supabase = getSupabase()

      // Read the length preference once on mount. The swiper page remounts on
      // route changes (Next App Router), so picking it up here naturally
      // refreshes after a visit to /account.
      lineMaxRef.current = readLineMax()

      // getUser() makes a server-validated request — always returns the live
      // user object including email, unlike getSession() which decodes the
      // cached JWT and may miss an email that was attached after token issuance.
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) {
        const { data, error } = await supabase.auth.signInAnonymously()
        if (error) console.error('Auth error:', error)
        else {
          userIdRef.current = data.user?.id ?? null
        }
      } else {
        userIdRef.current = user.id
        setUserEmail(user.email ?? null)
        isSignedInRef.current = user.is_anonymous === false
      }

      // If the user just signed in (came back from /auth/callback), the
      // migration RPC has already run, so any pre-sign-in anon deck state is
      // stale — drop it. Otherwise consider restoring it below.
      const saved = readSavedDeckState()
      const savedIsFresh =
        saved !== null && Date.now() - saved.timestamp <= DECK_STATE_TTL_MS
      if (saved && isSignedInRef.current) {
        clearSavedDeckState()
      }

      // Signed-in users get batches from recommend_poems and skip the pool.
      // For anon users build the pool unconditionally — even on a successful
      // restore the next prefetch will need it.
      if (!isSignedInRef.current) {
        let idQuery = supabase.from('poems').select('id')
        if (lineMaxRef.current !== null) {
          idQuery = idQuery.lte('line_count', lineMaxRef.current)
        }
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
      if (
        saved &&
        !isSignedInRef.current &&
        savedIsFresh &&
        saved.poemIds.length > 0
      ) {
        const { data, error: fetchErr } = await supabase
          .from('poems')
          .select('id, title, author, body, line_count')
          .in('id', saved.poemIds)
        if (!fetchErr && data) {
          const byId = new Map((data as Poem[]).map((p) => [p.id, p]))
          const ordered = saved.poemIds
            .map((id) => byId.get(id))
            .filter(Boolean) as Poem[]
          if (ordered.length > 0) {
            setPoems(ordered)
            setCardIdx(Math.min(saved.currentIndex, ordered.length - 1))
            restored = true
          }
        }
      }

      if (!restored) {
        await loadBatch()
      }

      if (userIdRef.current) {
        fetchSavedCount(userIdRef.current).then(setSavedCount)
      }

      setReady(true)
    }
    init()
  }, [loadBatch])

  // ── Prefetch next batch when approaching end of deck ──────────────────────
  useEffect(() => {
    if (ready && poems.length - cardIdx <= PREFETCH_AT) {
      loadBatch()
    }
  }, [cardIdx, poems.length, ready, loadBatch])

  // ── Persist deck state so a /account detour can be resumed ────────────────
  // Saves on every batch load and every swipe. Clears when the deck has been
  // fully consumed (cardIdx past the last loaded card) so the next session
  // doesn't resume into an empty pile. Sign-in clearing happens in init().
  useEffect(() => {
    if (!ready) return
    if (poems.length === 0) return
    if (cardIdx >= poems.length) {
      clearSavedDeckState()
      return
    }
    const state: SavedDeckState = {
      poemIds: poems.map((p) => p.id),
      currentIndex: cardIdx,
      timestamp: Date.now(),
    }
    try {
      localStorage.setItem(DECK_STATE_KEY, JSON.stringify(state))
    } catch {}
  }, [poems, cardIdx, ready])

  // ── Action handlers ────────────────────────────────────────────────────────
  const handlePreviewSkip = useCallback((poem: Poem) => {
    logInteraction(poem.id, 'dislike')
    setCardIdx((i) => i + 1)
  }, [logInteraction])

  const handlePreviewOpen = useCallback((poem: Poem) => {
    logInteraction(poem.id, 'preview_open')
    setOpenPoem(poem)
  }, [logInteraction])

  const handleFullPoemAction = useCallback((poem: Poem, action: FullPoemAction) => {
    const dbAction = action === 'skip' ? 'dislike' : action
    logInteraction(poem.id, dbAction)
    if (action === 'save' || action === 'super_like') {
      const newCount = savedCount + 1
      setSavedCount(newCount)
      // Only nudge anonymous users; only one modal at a time
      if (!userEmail && nudgeThreshold === null) {
        const threshold = getNextNudgeThreshold(newCount)
        if (threshold !== null) setNudgeThreshold(threshold)
      }
    }
    setOpenPoem(null)
    setCardIdx((i) => i + 1)
  }, [logInteraction, savedCount, userEmail, nudgeThreshold])

  // ── Render ─────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="h-dvh flex items-center justify-center bg-[#FAF6E9]">
        <p className="text-sm font-sans text-neutral-400">{error}</p>
      </div>
    )
  }

  if (!ready) {
    return (
      <div className="h-dvh flex items-center justify-center bg-[#FAF6E9]">
        <span className="text-sm font-sans text-neutral-300 tracking-widest">·  ·  ·</span>
      </div>
    )
  }

  const topPoem = poems[cardIdx]
  const nextPoem = poems[cardIdx + 1]

  return (
    <main className="relative h-dvh flex flex-col items-center overflow-hidden select-none bg-[#FAF6E9]">

      {/* ── Row 1: sign-in (left) · library (right) ──
          Both sides use the same 40px-tall flex frame so the 10px texts on
          left and right are anchored to the same vertical center as each
          other, regardless of the logo's mass on the right. */}
      <div className="w-full flex items-center justify-between px-6 pt-3 shrink-0">
        <div className="flex items-center h-10">
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
        <Link
          href="/library"
          aria-label="Library"
          className="flex items-center gap-1 h-10 hover:opacity-70 transition-opacity"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/sheaf-logo.png" alt="sheaf" width={40} height={40}
               style={{ objectFit: 'contain' }} className="block" />
          {savedCount > 0 && (
            <span className="text-[10px] leading-none font-sans tracking-wide tabular-nums text-neutral-400">
              {savedCount}
            </span>
          )}
        </Link>
      </div>

      {/* ── Row 2: masthead ── */}
      <div className="pt-1 pb-2 shrink-0">
        <Masthead />
      </div>

      {/* ── Card area: fills remaining space; card + action-row stacked, centered ── */}
      <div className="flex-1 flex items-center justify-center w-full min-h-0">
        {/* Card-area width. Mobile (<400px viewport) drops the 360px cap and
            uses a fixed 13px margin per side (100vw − 26px), which keeps
            sonnet titles to two lines at 390px wide. From 400px up, the 360px
            cap reapplies so the desktop reading column is unchanged. Both
            branches keep the height-bound term: at aspect 5:8, the card width
            cannot exceed (available_height × 5/8). */}
        <div className="flex flex-col items-stretch gap-5 shrink-0 w-[min(calc(100vw-26px),calc((100dvh-220px)*5/8))] min-[400px]:w-[min(360px,calc((100dvh-220px)*5/8))]">
          <div className="relative w-full" style={{ aspectRatio: '5 / 8' }}>
            {nextPoem && (
              <div
                key={nextPoem.id + '-bg'}
                className="absolute inset-0 rounded-2xl bg-[#F4ECC8] shadow-sm"
                style={{ transform: 'scale(0.96) translateY(8px)', opacity: 0.6, zIndex: 1 }}
              />
            )}
            {topPoem && (
              <SwipeCard
                key={topPoem.id}
                poem={topPoem}
                preview={getPreview(topPoem.body)}
                onOpen={() => handlePreviewOpen(topPoem)}
              />
            )}
          </div>

          {topPoem && (
            <div className="flex gap-2.5 w-full">
              <button
                type="button"
                onClick={() => handlePreviewSkip(topPoem)}
                aria-label="Skip"
                className="flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-[0.14em] uppercase border border-neutral-300 rounded-full text-neutral-500 hover:border-neutral-500 hover:text-neutral-700 transition-colors min-h-[44px]"
              >
                skip
              </button>
              <button
                type="button"
                onClick={() => handlePreviewOpen(topPoem)}
                aria-label="Read"
                className="flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-[0.14em] uppercase border border-neutral-300 rounded-full text-neutral-500 hover:border-neutral-500 hover:text-neutral-700 transition-colors min-h-[44px]"
              >
                read
              </button>
            </div>
          )}
        </div>
      </div>

      <AnimatePresence>
        {openPoem && (
          <FullPoemView
            key={openPoem.id + '-full'}
            poem={openPoem}
            onAction={(action) => handleFullPoemAction(openPoem, action)}
            onClose={() => setOpenPoem(null)}
          />
        )}
      </AnimatePresence>

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
