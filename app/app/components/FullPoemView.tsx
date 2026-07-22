'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Poem } from '../types'
import { ShareButton } from './ShareButton'

type SwipeAction = 'dislike' | 'save' | 'next'

interface SwipeProps {
  variant?: 'swipe'
  poem: Poem
  isSuperLiked?: never
  onAction: (action: SwipeAction) => void
  onUnsave?: never
  onUnskip?: never
  onClose: () => void
  // Renders inside the swipe deck card slot instead of as a full-screen overlay.
  // Suppresses the slide-up animation and the × close button.
  asCard?: boolean
  canUndo?: boolean
  onUndo?: () => void
}

interface LibraryProps {
  variant: 'library'
  poem: Poem
  isSuperLiked?: boolean
  onAction?: never
  onUnsave: () => void
  onUnskip?: never
  onClose: () => void
}

interface SkippedProps {
  variant: 'skipped'
  poem: Poem
  isSuperLiked?: never
  onAction?: never
  onUnsave?: never
  onUnskip: () => void
  onClose: () => void
}

type Props = SwipeProps | LibraryProps | SkippedProps


export function FullPoemView(props: Props) {
  const { poem } = props
  const isLibrary = props.variant === 'library'
  const isSkipped = props.variant === 'skipped'
  const asCard = !isLibrary && !isSkipped && !!(props as SwipeProps).asCard

  const [tapped, setTapped] = useState<string | null>(null)

  function handleSwipeAction(action: SwipeAction) {
    if (!props.onAction) return
    setTapped(action)
    props.onAction(action)
  }

  function handleUnsave() {
    if (!props.onUnsave) return
    setTapped('unsave')
    setTimeout(() => props.onUnsave!(), 180)
  }

  function handleUnskip() {
    if (!props.onUnskip) return
    setTapped('unskip')
    setTimeout(() => props.onUnskip!(), 180)
  }

  function handleClose() {
    if (!props.onClose) return
    props.onClose()
  }

  const inner = (
    <>
      {/* Back button — swipe overlay only; hidden in asCard mode (nothing to go back to)
          and in library/skipped variants. */}
      {!isLibrary && !isSkipped && !asCard && (
        <div className="absolute top-4 left-5 h-[1.4rem] inline-flex items-center z-10">
          <button
            onClick={handleClose}
            aria-label="Back"
            className="text-[1.4rem] leading-none text-neutral-500 hover:text-neutral-700 transition-colors"
          >
            ×
          </button>
        </div>
      )}

      {/* Share button — all variants; same vertical centre as the X close glyph. */}
      <div className="absolute top-4 right-5 h-[1.4rem] inline-flex items-center z-10">
        <ShareButton poemId={poem.id} title={poem.title} author={poem.author} />
      </div>

      {/* Scrollable poem */}
      <div className="flex-1 overflow-y-auto overscroll-contain px-6 sm:px-10 pt-14 pb-6 sm:pb-12">
        <h1 className="font-serif text-[1.5rem] leading-[1.35] font-normal text-[#111] mb-10">
          {poem.title}
          {isLibrary && 'isSuperLiked' in props && props.isSuperLiked && (
            <span className="ml-2 text-[1rem]" aria-label="Loved">💖</span>
          )}
        </h1>

        <div className="font-serif text-[1.05rem] leading-[1.95] text-[#111]">
          {poem.body.split('\n').map((line, i) =>
            line
              ? <span key={i} className="poem-line">{line}</span>
              : <span key={i} className="block">{' '}</span>
          )}
        </div>

        <p className="font-sans text-[0.9rem] italic text-neutral-400 mt-10 mb-2">
          {poem.author}
        </p>
      </div>

      {/* Action buttons */}
      {isLibrary ? (
        <div className="flex gap-2.5 px-6 py-5 border-t border-[rgba(0,0,0,0.08)] bg-[#ECECEC]">
          <button
            onClick={handleUnsave}
            className={`flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-wide border rounded-full transition-colors
              ${tapped === 'unsave'
                ? 'border-neutral-300 text-neutral-300'
                : 'border-neutral-300 text-neutral-400 hover:border-neutral-500 hover:text-neutral-600'}`}
          >
            Unsave
          </button>

          <button
            onClick={handleClose}
            className="flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-wide rounded-full transition-colors bg-[#111] text-white hover:bg-neutral-700"
          >
            Close
          </button>
        </div>
      ) : isSkipped ? (
        <div className="flex gap-2.5 px-6 py-5 border-t border-[rgba(0,0,0,0.08)] bg-[#ECECEC]">
          <button
            onClick={handleUnskip}
            className={`flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-wide border rounded-full transition-colors
              ${tapped === 'unskip'
                ? 'border-neutral-300 text-neutral-300'
                : 'border-neutral-300 text-neutral-400 hover:border-neutral-500 hover:text-neutral-600'}`}
          >
            Un-skip
          </button>

          <button
            onClick={handleClose}
            className="flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-wide rounded-full transition-colors bg-[#111] text-white hover:bg-neutral-700"
          >
            Close
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3 px-5 py-4 border-t border-[rgba(0,0,0,0.08)] bg-[#ECECEC]">
          {/* Undo — yellow circle, leftmost, hidden until there's something to undo */}
          <button
            onClick={(props as SwipeProps).onUndo}
            title="Undo"
            aria-label="Undo last action"
            className={`w-10 h-10 min-w-[40px] rounded-full bg-yellow-400 flex items-center justify-center shrink-0 transition-opacity ${(props as SwipeProps).canUndo ? 'opacity-80 hover:opacity-100' : 'opacity-0 pointer-events-none'}`}
          >
            <span className="text-white text-[1.1rem] leading-none select-none">↩</span>
          </button>

          {/* Dislike — ghost outlined, X icon */}
          <button
            onClick={() => handleSwipeAction('dislike')}
            title="Dislike"
            aria-label="Dislike"
            className={`flex-1 h-11 rounded-full border border-[rgba(0,0,0,0.15)] bg-transparent flex items-center justify-center transition-opacity min-h-[44px] ${tapped === 'dislike' ? 'opacity-30' : 'opacity-70 hover:opacity-100'}`}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>

          {/* Star — primary action, dark filled circle, larger and slightly lower */}
          <button
            onClick={() => handleSwipeAction('save')}
            title="Star"
            aria-label="Star"
            className={`w-14 h-14 min-w-[56px] rounded-full bg-[#111] flex items-center justify-center shrink-0 translate-y-2 transition-opacity ${tapped === 'save' ? 'opacity-30' : 'opacity-90 hover:opacity-100'}`}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="white" stroke="none" aria-hidden="true">
              <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
            </svg>
          </button>

          {/* Next — ghost outlined, right-arrow icon */}
          <button
            onClick={() => handleSwipeAction('next')}
            title="Next"
            aria-label="Next poem"
            className={`flex-1 h-11 rounded-full border border-[rgba(0,0,0,0.15)] bg-transparent flex items-center justify-center transition-opacity min-h-[44px] ${tapped === 'next' ? 'opacity-30' : 'opacity-70 hover:opacity-100'}`}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12,5 19,12 12,19" />
            </svg>
          </button>
        </div>
      )}
    </>
  )

  if (asCard) {
    return (
      <div className="absolute inset-0 overflow-hidden flex flex-col">
        {inner}
      </div>
    )
  }

  return (
    <motion.div
      initial={{ y: '100%' }}
      animate={{ y: 0 }}
      exit={{ y: '100%' }}
      transition={{ type: 'spring', damping: 34, stiffness: 290 }}
      className="fixed inset-0 z-50 flex flex-col bg-[#ECECEC]"
    >
      {inner}
    </motion.div>
  )
}
