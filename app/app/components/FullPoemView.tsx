'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Poem } from '../types'

type SwipeAction = 'skip' | 'save' | 'super_like'

interface SwipeProps {
  variant?: 'swipe'
  poem: Poem
  isSuperLiked?: never
  onAction: (action: SwipeAction) => void
  onUnsave?: never
  onClose?: never
}

interface LibraryProps {
  variant: 'library'
  poem: Poem
  isSuperLiked?: boolean
  onAction?: never
  onUnsave: () => void
  onClose: () => void
}

type Props = SwipeProps | LibraryProps

export function FullPoemView(props: Props) {
  const { poem } = props
  const isLibrary = props.variant === 'library'

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

  function handleClose() {
    if (!props.onClose) return
    props.onClose()
  }

  return (
    <motion.div
      initial={{ y: '100%' }}
      animate={{ y: 0 }}
      exit={{ y: '100%' }}
      transition={{ type: 'spring', damping: 34, stiffness: 290 }}
      className="fixed inset-0 z-50 flex flex-col bg-[#faf9f7]"
    >
      {/* Scrollable poem */}
      <div className="flex-1 overflow-y-auto overscroll-contain px-8 pt-14 pb-6">
        <h1 className="font-serif text-[1.5rem] leading-[1.35] font-normal text-[#111] mb-10">
          {poem.title}
          {isLibrary && props.isSuperLiked && (
            <span className="ml-2 text-[1rem]" aria-label="Loved">💖</span>
          )}
        </h1>

        <div className="font-serif text-[1.05rem] leading-[1.95] text-[#111] whitespace-pre-wrap">
          {poem.body}
        </div>

        <p className="font-sans text-[0.8rem] italic text-neutral-400 mt-10 mb-2">
          {poem.author}
        </p>
      </div>

      {/* Action buttons */}
      {isLibrary ? (
        <div className="flex gap-2.5 px-6 py-5 border-t border-neutral-100 bg-[#faf9f7]">
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
      ) : (
        <div className="flex gap-2.5 px-6 py-5 border-t border-neutral-100 bg-[#faf9f7]">
          <button
            onClick={() => handleSwipeAction('skip')}
            title="Skip"
            aria-label="Skip"
            className={`flex-1 py-3 text-[1.5rem] leading-none transition-opacity rounded-full min-h-[44px]
              ${tapped === 'skip' ? 'opacity-30' : 'opacity-70 hover:opacity-100'}`}
          >
            🤷
          </button>

          <button
            onClick={() => handleSwipeAction('save')}
            title="Like"
            aria-label="Like"
            className={`flex-1 py-3 text-[1.5rem] leading-none border rounded-full transition-all min-h-[44px]
              ${tapped === 'save'
                ? 'bg-[#111] border-[#111] opacity-50'
                : 'border-[#111] opacity-80 hover:opacity-100 hover:bg-[#111]'}`}
          >
            👍
          </button>

          <button
            onClick={() => handleSwipeAction('super_like')}
            title="Love"
            aria-label="Love"
            className={`flex-1 py-3 text-[1.5rem] leading-none rounded-full transition-all min-h-[44px]
              ${tapped === 'super_like'
                ? 'bg-neutral-500 opacity-50'
                : 'bg-[#111] opacity-90 hover:opacity-100 hover:bg-neutral-700'}`}
          >
            💖
          </button>
        </div>
      )}
    </motion.div>
  )
}
