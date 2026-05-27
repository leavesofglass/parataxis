'use client'

import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { getSupabase } from '@/lib/supabase'
import { fetchLibrary, fetchSkipped } from '@/lib/library'
import type { LibraryPoem, SkippedPoem } from '@/lib/library'
import { FullPoemView } from './FullPoemView'

function getFirstLines(body: string, n = 2): string {
  return body
    .split('\n')
    .filter((l) => l.trim() !== '')
    .slice(0, n)
    .join('\n')
}

export function LibraryList() {
  const userIdRef = useRef<string | null>(null)
  const [poems, setPoems] = useState<LibraryPoem[]>([])
  const [skipped, setSkipped] = useState<SkippedPoem[]>([])
  const [openPoem, setOpenPoem] = useState<LibraryPoem | null>(null)
  const [openSkippedPoem, setOpenSkippedPoem] = useState<SkippedPoem | null>(null)
  const [skippedExpanded, setSkippedExpanded] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    async function init() {
      const supabase = getSupabase()

      const { data: { session } } = await supabase.auth.getSession()
      if (session) {
        userIdRef.current = session.user.id
      } else {
        const { data, error } = await supabase.auth.signInAnonymously()
        if (error) console.error('Auth error:', error)
        else userIdRef.current = data.user?.id ?? null
      }

      if (!userIdRef.current) {
        setReady(true)
        return
      }

      const [library, skips] = await Promise.all([
        fetchLibrary(userIdRef.current),
        fetchSkipped(userIdRef.current),
      ])
      setPoems(library)
      setSkipped(skips)
      setReady(true)
    }
    init()
  }, [])

  function handleUnsave(poem: LibraryPoem) {
    const userId = userIdRef.current
    if (!userId) return

    // Fire-and-forget unsave interaction
    void getSupabase()
      .from('interactions')
      .insert({ user_id: userId, poem_id: poem.id, action: 'unsave' })
      .then((res: { error: unknown }) => {
        if (res.error) console.error('unsave insert failed:', res.error)
      })

    setOpenPoem(null)
    setPoems((prev) => prev.filter((p) => p.id !== poem.id))
  }

  function handleUnskip(poem: SkippedPoem) {
    const userId = userIdRef.current
    if (!userId) return

    // Optimistically remove from the list. Then delete the dislike row plus
    // any preview_open / preview_skip rows for this poem, so the recommender
    // (which excludes any-interaction poems) can resurface it.
    setOpenSkippedPoem(null)
    setSkipped((prev) => prev.filter((p) => p.id !== poem.id))

    void getSupabase()
      .from('interactions')
      .delete()
      .eq('user_id', userId)
      .eq('poem_id', poem.id)
      .in('action', ['dislike', 'preview_open', 'preview_skip'])
      .then(({ error }: { error: unknown }) => {
        if (error) console.error('un-skip delete failed:', error)
      })
  }

  if (!ready) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-sm font-sans text-neutral-300 tracking-widest">·  ·  ·</span>
      </div>
    )
  }

  if (poems.length === 0 && skipped.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-8 text-center gap-4">
        <p className="font-serif text-[1rem] leading-[1.7] text-neutral-400">
          Nothing saved yet.
          <br />
          Tap a poem to read, then save the ones you want to keep.
        </p>
        <a
          href="/"
          className="text-[0.75rem] font-sans tracking-[0.14em] uppercase text-neutral-400 hover:text-neutral-600 transition-colors"
        >
          Back to discovery
        </a>
      </div>
    )
  }

  return (
    <>
      <div className="flex-1 overflow-y-auto overscroll-contain px-6 pt-4 pb-8">
        {poems.length > 0 && (
          <ul>
            <AnimatePresence initial={false}>
              {poems.map((poem) => (
                <motion.li
                  key={poem.id}
                  layout
                  initial={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                  transition={{ duration: 0.28, ease: 'easeInOut' }}
                  className="overflow-hidden"
                >
                  <button
                    onClick={() => setOpenPoem(poem)}
                    className="w-full text-left py-5 border-b border-neutral-100 last:border-0"
                  >
                    <p className="font-sans text-[0.7rem] font-medium tracking-[0.14em] text-neutral-400 uppercase mb-1.5">
                      {poem.title}
                      {poem.isSuperLiked && (
                        <span className="ml-1.5 text-[0.85rem]" aria-label="Loved">💖</span>
                      )}
                    </p>
                    <p className="font-sans text-[0.7rem] italic text-neutral-300 mb-2.5">
                      {poem.author}
                    </p>
                    <p className="font-serif text-[0.95rem] leading-[1.75] text-[#555] whitespace-pre-wrap">
                      {getFirstLines(poem.body)}
                    </p>
                  </button>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}

        {skipped.length > 0 && (
          <section
            className={poems.length > 0 ? 'mt-6 pt-2 border-t border-neutral-200' : ''}
          >
            <button
              onClick={() => setSkippedExpanded((e) => !e)}
              aria-expanded={skippedExpanded}
              className="w-full flex items-baseline justify-between py-4 group"
            >
              <span className="flex items-baseline gap-2">
                <span className="font-sans text-[0.7rem] tracking-[0.14em] text-neutral-400 uppercase group-hover:text-neutral-600 transition-colors">
                  Skipped
                </span>
                <span className="font-sans text-[0.7rem] tabular-nums text-neutral-300">
                  {skipped.length}
                </span>
              </span>
              <span className="font-sans text-[0.65rem] tracking-[0.14em] text-neutral-300 group-hover:text-neutral-500 transition-colors uppercase">
                {skippedExpanded ? 'Hide' : 'Show'}
              </span>
            </button>

            {skippedExpanded && (
              <ul>
                <AnimatePresence initial={false}>
                  {skipped.map((poem) => (
                    <motion.li
                      key={poem.id}
                      layout
                      initial={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                      transition={{ duration: 0.28, ease: 'easeInOut' }}
                      className="overflow-hidden"
                    >
                      <div className="flex items-start gap-3 py-4 border-b border-neutral-100 last:border-0 opacity-60">
                        <button
                          onClick={() => setOpenSkippedPoem(poem)}
                          className="flex-1 text-left"
                        >
                          <p className="font-sans text-[0.65rem] font-medium tracking-[0.14em] text-neutral-400 uppercase mb-1.5">
                            {poem.title}
                          </p>
                          <p className="font-sans text-[0.65rem] italic text-neutral-300 mb-2.5">
                            {poem.author}
                          </p>
                          <p className="font-serif text-[0.85rem] leading-[1.7] text-[#777] whitespace-pre-wrap">
                            {getFirstLines(poem.body)}
                          </p>
                        </button>
                        <button
                          onClick={() => handleUnskip(poem)}
                          aria-label="Remove from skipped"
                          className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full text-[1.1rem] leading-none text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 transition-colors"
                        >
                          ×
                        </button>
                      </div>
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            )}
          </section>
        )}
      </div>

      <AnimatePresence>
        {openPoem && (
          <FullPoemView
            key={openPoem.id + '-library'}
            variant="library"
            poem={openPoem}
            isSuperLiked={openPoem.isSuperLiked}
            onUnsave={() => handleUnsave(openPoem)}
            onClose={() => setOpenPoem(null)}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {openSkippedPoem && (
          <FullPoemView
            key={openSkippedPoem.id + '-skipped'}
            variant="skipped"
            poem={openSkippedPoem}
            onUnskip={() => handleUnskip(openSkippedPoem)}
            onClose={() => setOpenSkippedPoem(null)}
          />
        )}
      </AnimatePresence>
    </>
  )
}
