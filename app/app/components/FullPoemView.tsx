'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Poem } from '../types'

type Action = 'skip' | 'save' | 'super_like'

interface Props {
  poem: Poem
  onAction: (action: Action) => void
}

const ACTIONS: { key: Action; label: string }[] = [
  { key: 'skip', label: 'Skip' },
  { key: 'save', label: 'Save' },
  { key: 'super_like', label: 'Super-like' },
]

export function FullPoemView({ poem, onAction }: Props) {
  const [tapped, setTapped] = useState<Action | null>(null)

  function handleAction(action: Action) {
    setTapped(action)
    // brief visual feedback before dismissing
    setTimeout(() => onAction(action), 180)
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
        </h1>

        <div className="font-serif text-[1.05rem] leading-[1.95] text-[#111] whitespace-pre-wrap">
          {poem.body}
        </div>

        <p className="font-sans text-[0.8rem] italic text-neutral-400 mt-10 mb-2">
          {poem.author}
        </p>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2.5 px-6 py-5 border-t border-neutral-100 bg-[#faf9f7]">
        <button
          onClick={() => handleAction('skip')}
          className={`flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-wide transition-colors rounded-full
            ${tapped === 'skip' ? 'text-neutral-300' : 'text-neutral-400 hover:text-neutral-600'}`}
        >
          Skip
        </button>

        <button
          onClick={() => handleAction('save')}
          className={`flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-wide border rounded-full transition-colors
            ${tapped === 'save'
              ? 'bg-[#111] border-[#111] text-white'
              : 'border-[#111] text-[#111] hover:bg-[#111] hover:text-white'}`}
        >
          Save
        </button>

        <button
          onClick={() => handleAction('super_like')}
          className={`flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-wide rounded-full transition-colors
            ${tapped === 'super_like'
              ? 'bg-neutral-500 text-white'
              : 'bg-[#111] text-white hover:bg-neutral-700'}`}
        >
          Super-like
        </button>
      </div>
    </motion.div>
  )
}
