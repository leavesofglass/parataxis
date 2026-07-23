'use client'

import { motion } from 'framer-motion'
import type { Poem } from '../types'
import { ShareButton } from './ShareButton'

export interface Reactions {
  liked: boolean
  disliked: boolean
  saved: boolean
}

interface SwipeProps {
  variant?: 'swipe'
  poem: Poem
  isSuperLiked?: never
  activeReactions: Reactions
  onReaction: (action: 'like' | 'dislike' | 'save') => void
  onNext: () => void
  onShare: () => void
  onUnsave?: never
  onUnskip?: never
  onClose: () => void
  asCard?: boolean
  canBack?: boolean
  onBack?: () => void
}

interface LibraryProps {
  variant: 'library'
  poem: Poem
  isSuperLiked?: boolean
  activeReactions?: never
  onReaction?: never
  onNext?: never
  onShare?: never
  onUnsave: () => void
  onUnskip?: never
  onClose: () => void
}

interface SkippedProps {
  variant: 'skipped'
  poem: Poem
  isSuperLiked?: never
  activeReactions?: never
  onReaction?: never
  onNext?: never
  onShare?: never
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

  const swipe = (!isLibrary && !isSkipped) ? (props as SwipeProps) : null

  function handleClose() {
    props.onClose()
  }

  const inner = (
    <>
      {/* Back button — swipe overlay only; hidden in asCard mode and library/skipped */}
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

      {/* Top-right column: Share above Save ribbon — pinned above scroll */}
      <div className="absolute top-4 right-5 z-10 flex flex-col items-center gap-3">
        <ShareButton
          poemId={poem.id}
          title={poem.title}
          author={poem.author}
          onSuccess={swipe?.onShare}
        />

        {swipe && (
          <button
            type="button"
            onClick={() => swipe.onReaction('save')}
            aria-label={swipe.activeReactions.saved ? 'Unsave poem' : 'Save poem'}
            className="inline-flex items-center justify-center text-neutral-500 hover:text-neutral-700 transition-colors"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill={swipe.activeReactions.saved ? 'currentColor' : 'none'}
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
              className={swipe.activeReactions.saved ? 'text-neutral-700' : 'text-neutral-400'}
            >
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
            </svg>
          </button>
        )}
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
              : <span key={i} className="block">{' '}</span>
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
            onClick={() => { if (props.onUnsave) props.onUnsave() }}
            className="flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-wide border border-neutral-300 text-neutral-400 hover:border-neutral-500 hover:text-neutral-600 rounded-full transition-colors"
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
            onClick={() => { if (props.onUnskip) props.onUnskip() }}
            className="flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-wide border border-neutral-300 text-neutral-400 hover:border-neutral-500 hover:text-neutral-600 rounded-full transition-colors"
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
      ) : swipe ? (
        <div className="relative flex items-center justify-center py-4 border-t border-[rgba(0,0,0,0.08)] bg-[#ECECEC]">
          {/* Back — absolutely positioned left so it doesn't displace the centered trio */}
          <button
            onClick={swipe.onBack}
            title="Back"
            aria-label="Back"
            className={`absolute left-5 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full border border-[rgba(0,0,0,0.15)] bg-transparent flex items-center justify-center transition-opacity ${swipe.canBack ? 'opacity-70 hover:opacity-100' : 'opacity-0 pointer-events-none'}`}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="9,14 4,9 9,4" /><path d="M20,20 v-7 a4,4 0 0,0 -4,-4 H4" />
            </svg>
          </button>

          {/* Like · Dislike · Next — centered as a group */}
          <div className="flex items-center gap-3">
            {/* Like — heart; filled + dark when active */}
            <button
              onClick={() => swipe.onReaction('like')}
              title="Like"
              aria-label="Like"
              className={`w-20 h-11 rounded-full border flex items-center justify-center transition-colors min-h-[44px]
                ${swipe.activeReactions.liked
                  ? 'border-neutral-500 text-neutral-700'
                  : 'border-[rgba(0,0,0,0.15)] text-neutral-400 hover:border-neutral-400 hover:text-neutral-500'}`}
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill={swipe.activeReactions.liked ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
              </svg>
            </button>

            {/* Dislike — X; darkened + slight bg when active */}
            <button
              onClick={() => swipe.onReaction('dislike')}
              title="Dislike"
              aria-label="Dislike"
              className={`w-20 h-11 rounded-full border flex items-center justify-center transition-colors min-h-[44px]
                ${swipe.activeReactions.disliked
                  ? 'border-neutral-500 text-neutral-700 bg-neutral-100'
                  : 'border-[rgba(0,0,0,0.15)] text-neutral-400 hover:border-neutral-400 hover:text-neutral-500'}`}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>

            {/* Next — always ghost; the only advancing action */}
            <button
              onClick={swipe.onNext}
              title="Next"
              aria-label="Next poem"
              className="w-20 h-11 rounded-full border border-[rgba(0,0,0,0.15)] text-neutral-400 bg-transparent flex items-center justify-center transition-colors min-h-[44px] hover:border-neutral-400 hover:text-neutral-500"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12,5 19,12 12,19" />
              </svg>
            </button>
          </div>
        </div>
      ) : null}
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
