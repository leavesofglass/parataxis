'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { getSupabase } from '@/lib/supabase'
import type { Poem } from '../types'
import { SwipeCard } from './SwipeCard'
import { FullPoemView } from './FullPoemView'

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
  // trim to 240 chars at a word boundary
  return text.slice(0, 240).replace(/\s+\S*$/, '') + '…'
}

export function PoemSwiper() {
  const poolRef = useRef<string[]>([])
  const poolPosRef = useRef(0)
  const fetchingRef = useRef(false)

  const [poems, setPoems] = useState<Poem[]>([])
  const [cardIdx, setCardIdx] = useState(0)
  const [openPoem, setOpenPoem] = useState<Poem | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadBatch = useCallback(async () => {
    if (fetchingRef.current || poolRef.current.length === 0) return
    fetchingRef.current = true

    // Wrap around and reshuffle when pool is exhausted
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

    // Preserve the shuffle order of the batch
    const ordered = batch
      .map((id) => data.find((p: Poem) => p.id === id))
      .filter(Boolean) as Poem[]

    setPoems((prev) => [...prev, ...ordered])
  }, [])

  // Init: anon auth + fetch all IDs + load first batch
  useEffect(() => {
    async function init() {
      const supabase = getSupabase()

      // Silent anonymous auth
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        const { data, error } = await supabase.auth.signInAnonymously()
        if (error) console.error('Auth error:', error)
        else console.log('user_id:', data.user?.id)
      } else {
        console.log('user_id:', session.user.id)
      }

      // Fetch all poem IDs (599 rows × ~10 bytes ≈ 6 KB)
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
      setReady(true)
    }
    init()
  }, [loadBatch])

  // Prefetch next batch when approaching the end of loaded cards
  useEffect(() => {
    if (ready && poems.length - cardIdx <= PREFETCH_AT) {
      loadBatch()
    }
  }, [cardIdx, poems.length, ready, loadBatch])

  const advance = useCallback(() => {
    setOpenPoem(null)
    setCardIdx((i) => i + 1)
  }, [])

  const handleOpen = useCallback((poem: Poem) => {
    setOpenPoem(poem)
  }, [])

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
      {/* Card stack */}
      <div className="relative w-4/5 max-w-sm" style={{ aspectRatio: '2 / 3' }}>
        {/* Background card (next poem) */}
        {nextPoem && (
          <div
            key={nextPoem.id + '-bg'}
            className="absolute inset-0 rounded-2xl bg-white shadow-sm"
            style={{ transform: 'scale(0.96) translateY(8px)', opacity: 0.6, zIndex: 1 }}
          />
        )}

        {/* Top card (current poem) */}
        {topPoem && (
          <SwipeCard
            key={topPoem.id}
            poem={topPoem}
            preview={getPreview(topPoem.body)}
            onSkip={advance}
            onOpen={() => handleOpen(topPoem)}
          />
        )}
      </div>

      {/* Hint */}
      <p className="mt-8 text-[10px] font-sans tracking-[0.2em] text-neutral-300 uppercase">
        ← skip · read →
      </p>

      {/* Full poem overlay */}
      <AnimatePresence>
        {openPoem && (
          <FullPoemView key={openPoem.id + '-full'} poem={openPoem} onAction={advance} />
        )}
      </AnimatePresence>
    </main>
  )
}
