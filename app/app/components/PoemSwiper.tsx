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

interface LastAction {
  poem: Poem
  action: FullPoemAction
  dbAction: string
}

// ── PoemCard ──────────────────────────────────────────────────────────────────
// Non-draggable card wrapper. Drives entry and exit animations via the animate
// prop rather than drag gestures. Entry animation fires only on undo (enterDir
// set); normal forward navigation uses initial=false (instant appear). Exit
// animation fires when exitingAction is set by a button press in PoemSwiper.
//
// onExited is guarded by exitingAction so it only fires on actual exit, not on
// the completion of an undo entry animation.
function PoemCard({
  poem,
  onAction,
  exitingAction,
  enterDir,
  onExited,
  canUndo,
  onUndo,
}: {
  poem: Poem
  onAction: (a: FullPoemAction) => void
  exitingAction: FullPoemAction | null
  enterDir: 'left' | 'right' | 'up' | null
  onExited: () => void
  canUndo: boolean
  onUndo: () => void
}) {
  const exitTarget: TargetAndTransition =
    exitingAction === 'skip'       ? { x: '-160%', opacity: 0 } :
    exitingAction === 'save'       ? { x: '160%',  opacity: 0 } :
    exitingAction === 'super_like' ? { y: '-160%', opacity: 0 } :
    { x: 0, y: 0, opacity: 1 }

  // On normal forward navigation: appear instantly (no entry animation).
  // On undo: slide in from the direction the previous card exited.
  const initial: TargetAndTransition | false =
    enterDir === 'left'  ? { x: '-100%', opacity: 0 } :
    enterDir === 'right' ? { x: '100%',  opacity: 0 } :
    enterDir === 'up'    ? { y: '100%',  opacity: 0 } :
    false

  return (
    <motion.div
      className="absolute inset-0"
      style={{ zIndex: 2 }}
      initial={initial}
      animate={exitTarget}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      onAnimationComplete={() => { if (exitingAction) onExited() }}
    >
      <FullPoemView
        poem={poem}
        onAction={onAction}
        onClose={() => {}}
        asCard
        canUndo={canUndo}
        onUndo={onUndo}
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
  const lineMaxRef = useRef<number | null>(null)

  // Holds the poem+action for the card currently mid-exit-animation, so
  // handleCardExited can read them without stale-closure risk.
  const pendingRef = useRef<{ poem: Poem; action: FullPoemAction } | null>(null)

  const [poems, setPoems] = useState<Poem[]>([])
  const [cardIdx, setCardIdx] = useState(0)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedCount, setSavedCount] = useState(0)
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [nudgeThreshold, setNudgeThreshold] = useState<NudgeThreshold | null>(null)

  // exitingAction drives the card's exit animation via PoemCard's animate prop.
  const [exitingAction, setExitingAction] = useState<FullPoemAction | null>(null)
  // enterDir drives the entry animation for the card that appears after undo.
  const [enterDir, setEnterDir] = useState<'left' | 'right' | 'up' | null>(null)
  // lastAction holds the most recently completed action for single-level undo.
  const [lastAction, setLastAction] = useState<LastAction | null>(null)

  // Undo button is visible only when there's something to undo AND the deck
  // isn't mid-animation (prevents undo during an exit).
  const canUndo = lastAction !== null && exitingAction === null

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
    const lineMax = lineMaxRef.current

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
      lineMaxRef.current = readLineMax()

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
        if (lineMaxRef.current !== null) idQuery = idQuery.lte('line_count', lineMaxRef.current)
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

  // ── Action handlers ───────────────────────────────────────────────────────

  // Called immediately when a button is pressed. Sets the exit animation and
  // captures the pending poem+action in a ref for handleCardExited to read.
  const handleButtonPress = useCallback((poem: Poem, action: FullPoemAction) => {
    if (pendingRef.current) return
    pendingRef.current = { poem, action }
    setEnterDir(null)
    setExitingAction(action)
  }, [])

  // Called by PoemCard's onAnimationComplete when the exit animation finishes.
  // Logs the interaction, updates counts, advances the deck, stores lastAction.
  const handleCardExited = useCallback(() => {
    const pending = pendingRef.current
    if (!pending) return
    pendingRef.current = null

    const { poem, action } = pending
    const dbAction = action === 'skip' ? 'dislike' : action
    logInteraction(poem.id, dbAction)

    setLastAction({ poem, action, dbAction })
    setExitingAction(null)

    if (action === 'save' || action === 'super_like') {
      const newCount = savedCount + 1
      setSavedCount(newCount)
      if (!userEmail && nudgeThreshold === null) {
        const threshold = getNextNudgeThreshold(newCount)
        if (threshold !== null) setNudgeThreshold(threshold)
      }
    }

    setCardIdx((i) => i + 1)
  }, [logInteraction, savedCount, userEmail, nudgeThreshold])

  // Single-level undo: deletes the most recent interaction row from Supabase
  // (SELECT id first, then DELETE by id), reverses savedCount if needed, and
  // returns the previous poem with a reversed entry animation.
  const handleUndo = useCallback(() => {
    if (!lastAction) return
    const { poem, action, dbAction } = lastAction

    const userId = userIdRef.current
    if (userId) {
      void getSupabase()
        .from('interactions')
        .select('id')
        .eq('user_id', userId)
        .eq('poem_id', poem.id)
        .eq('action', dbAction)
        .order('created_at', { ascending: false })
        .limit(1)
        .maybeSingle()
        .then(({ data }: { data: { id: string } | null }) => {
          if (data?.id) {
            void getSupabase()
              .from('interactions')
              .delete()
              .eq('id', data.id)
          }
        })
    }

    if (action === 'save' || action === 'super_like') {
      setSavedCount((c) => Math.max(0, c - 1))
    }

    // Slide the returning card in from the same direction the previous card exited.
    const reverse: 'left' | 'right' | 'up' =
      action === 'skip' ? 'left' :
      action === 'save' ? 'right' :
      'up'

    setEnterDir(reverse)
    setLastAction(null)
    pendingRef.current = null
    setExitingAction(null)
    setCardIdx((i) => i - 1)
  }, [lastAction])

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
  const nextPoem = poems[cardIdx + 1]

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
            className="flex items-center gap-1 hover:opacity-70 transition-opacity"
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
      </div>

      {/* ── Card area ── */}
      <div className="flex-1 flex items-center justify-center w-full min-h-0 py-4 px-[2.5vw] sm:px-0">
        <div className="relative h-full w-full max-w-[760px]">

          {topPoem && (
            <PoemCard
              key={topPoem.id}
              poem={topPoem}
              onAction={(action) => handleButtonPress(topPoem, action)}
              exitingAction={exitingAction}
              enterDir={enterDir}
              onExited={handleCardExited}
              canUndo={canUndo}
              onUndo={handleUndo}
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
