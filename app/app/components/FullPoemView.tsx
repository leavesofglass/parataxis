'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Poem } from '../types'
import { ShareButton } from './ShareButton'

type SwipeAction = 'skip' | 'save' | 'super_like'

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

// Shared class string — all three swipe action buttons are visually identical.
// Using border-neutral-900 (standard scale) instead of arbitrary border-[#111]
// to ensure Tailwind v4 reliably generates the CSS.
function actionBtnClass(action: string, tapped: string | null) {
  const base = 'flex-1 py-3 text-[1.5rem] leading-none border border-neutral-900 rounded-full transition-opacity min-h-[44px]'
  return tapped === action ? `${base} opacity-30` : `${base} opacity-80 hover:opacity-100`
}

export function FullPoemView(props: Props) {
  const { poem } = props
  const isLibrary = props.variant === 'library'
  const isSkipped = props.variant === 'skipped'
  const asCard = !isLibrary && !isSkipped && !!(props as SwipeProps).asCard

  const [tapped, setTapped] = useState<string | null>(null)

  function handleSwipeAction(action: SwipeAction) {
    if (!props.onAction) return
    setTapped(action)
    setTimeout(() => props.onAction!(action), 180)
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

        <div className="font-serif text-[1.05rem] leading-[1.95] text-[#111] whitespace-pre-wrap">
          {poem.body}
        </div>

        <p className="font-sans text-[0.9rem] italic text-neutral-400 mt-10 mb-2">
          {poem.author}
        </p>
      </div>

      {/* Action buttons */}
      {isLibrary ? (
        <div className="flex gap-2.5 px-6 py-5 border-t border-neutral-100 bg-[#F4ECC8]">
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
        <div className="flex gap-2.5 px-6 py-5 border-t border-neutral-100 bg-[#F4ECC8]">
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
        <div className="flex gap-2.5 px-6 py-5 border-t border-neutral-100 bg-[#F4ECC8]">
          <button onClick={() => handleSwipeAction('skip')} title="Skip" aria-label="Skip" className={actionBtnClass('skip', tapped)}>🤷</button>
          <button onClick={() => handleSwipeAction('save')} title="Like" aria-label="Like" className={actionBtnClass('save', tapped)}>👍</button>
          <button onClick={() => handleSwipeAction('super_like')} title="Love" aria-label="Love" className={actionBtnClass('super_like', tapped)}>💖</button>
        </div>
      )}
    </>
  )

  if (asCard) {
    return (
      <div className="absolute inset-0 rounded-2xl overflow-hidden flex flex-col bg-[#F4ECC8]">
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
      className="fixed inset-0 z-50 flex flex-col bg-[#F4ECC8]"
    >
      {inner}
    </motion.div>
  )
}
