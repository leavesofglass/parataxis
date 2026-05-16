'use client'

import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { getSupabase } from '@/lib/supabase'
import { fetchLibrary } from '@/lib/library'
import type { LibraryPoem } from '@/lib/library'
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
  const [openPoem, setOpenPoem] = useState<LibraryPoem | null>(null)
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

      const library = await fetchLibrary(userIdRef.current)
      setPoems(library)
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

  if (!ready) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-sm font-sans text-neutral-300 tracking-widest">·  ·  ·</span>
      </div>
    )
  }

  if (poems.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-8 text-center gap-4">
        <p className="font-serif text-[1rem] leading-[1.7] text-neutral-400">
          Nothing saved yet.
          <br />
          Swipe and save poems to build your library.
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
      <ul className="flex-1 overflow-y-auto overscroll-contain px-6 pt-4 pb-8">
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
                    <span className="ml-1.5 text-neutral-300">★</span>
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
    </>
  )
}
