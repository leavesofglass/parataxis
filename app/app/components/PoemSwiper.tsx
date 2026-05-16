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

const BATCH = 20
const PREFETCH_AT = 5

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
    if (fetchingRef.current || poolRef.current.length === 0) return
    fetchingRef.current = true

    if (poolPosRef.current >= poolRef.current.length) {
      poolRef.current = shuffle(poolRef.current)
      poolPosRef.current = 0
    }

    const batch = poolRef.current.slice(poolPosRef.current, poolPosRef.current + BATCH)
    poolPosRef.current += batch.length

    const supabase = getSupabase()
    const { data, error } = await supabase
      .from('poems')
      .select('id, title, author, body, line_count')
      .in('id', batch)

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
      }
    )
    return () => subscription.unsubscribe()
  }, [])

  // ── Init: anon auth + fetch all IDs + first batch ─────────────────────────
  useEffect(() => {
    async function init() {
      const supabase = getSupabase()

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
      }

      const { data: idRows, error: idError } = await supabase
        .from('poems')
        .select('id')

      if (idError || !idRows) {
        console.error('poems select failed:', JSON.stringify(idError))
        setError(`Could not load poems. (${idError?.code ?? 'unknown'}: ${idError?.message ?? 'no data'})`)
        return
      }

      poolRef.current = shuffle(idRows.map((r: { id: string }) => r.id))
      poolPosRef.current = 0

      await loadBatch()

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

  // ── Action handlers ────────────────────────────────────────────────────────
  const handlePreviewSkip = useCallback((poem: Poem) => {
    logInteraction(poem.id, 'preview_skip')
    setCardIdx((i) => i + 1)
  }, [logInteraction])

  const handlePreviewOpen = useCallback((poem: Poem) => {
    logInteraction(poem.id, 'preview_open')
    setOpenPoem(poem)
  }, [logInteraction])

  const handleFullPoemAction = useCallback((poem: Poem, action: FullPoemAction) => {
    const dbAction = action === 'skip' ? 'preview_skip' : action
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
      <div className="h-dvh flex items-center justify-center bg-[#faf9f7]">
        <p className="text-sm font-sans text-neutral-400">{error}</p>
      </div>
    )
  }

  if (!ready) {
    return (
      <div className="h-dvh flex items-center justify-center bg-[#faf9f7]">
        <span className="text-sm font-sans text-neutral-300 tracking-widest">·  ·  ·</span>
      </div>
    )
  }

  const topPoem = poems[cardIdx]
  const nextPoem = poems[cardIdx + 1]

  return (
    <main className="h-dvh flex flex-col items-center justify-center select-none overflow-hidden bg-[#faf9f7]">
      {/* Account link */}
      <Link
        href="/account"
        className="absolute top-10 left-6 text-[10px] font-sans tracking-[0.18em] text-neutral-300 uppercase hover:text-neutral-500 transition-colors max-w-[120px] truncate"
      >
        {userEmail
          ? userEmail.length > 20
            ? 'Account'
            : userEmail
          : 'Sign in'}
      </Link>

      {/* Library badge */}
      <Link
        href="/library"
        aria-label="Library"
        className="absolute top-10 right-6 flex items-center gap-1 hover:opacity-70 transition-opacity"
      >
        <span className="text-[1.25rem] leading-none">📚</span>
        {savedCount > 0 && (
          <span className="text-[10px] font-sans tracking-wide tabular-nums text-neutral-400">
            {savedCount}
          </span>
        )}
      </Link>

      {/* Card stack */}
      <div className="relative w-4/5 max-w-sm" style={{ aspectRatio: '2 / 3' }}>
        {nextPoem && (
          <div
            key={nextPoem.id + '-bg'}
            className="absolute inset-0 rounded-2xl bg-white shadow-sm"
            style={{ transform: 'scale(0.96) translateY(8px)', opacity: 0.6, zIndex: 1 }}
          />
        )}
        {topPoem && (
          <SwipeCard
            key={topPoem.id}
            poem={topPoem}
            preview={getPreview(topPoem.body)}
            onSkip={() => handlePreviewSkip(topPoem)}
            onOpen={() => handlePreviewOpen(topPoem)}
          />
        )}
      </div>

      <p className="mt-8 text-[10px] font-sans tracking-[0.2em] text-neutral-300 uppercase">
        tap to read · ← skip
      </p>

      <AnimatePresence>
        {openPoem && (
          <FullPoemView
            key={openPoem.id + '-full'}
            poem={openPoem}
            onAction={(action) => handleFullPoemAction(openPoem, action)}
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
