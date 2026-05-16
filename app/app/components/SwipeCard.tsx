'use client'

import type { MouseEvent } from 'react'
import type { Poem } from '../types'

interface Props {
  poem: Poem
  preview: string
  onSkip: () => void
  onOpen: () => void
}

const actionBtn =
  'flex-1 py-3 text-[0.8rem] font-sans font-medium tracking-[0.14em] uppercase border border-neutral-300 rounded-full text-neutral-500 hover:border-neutral-500 hover:text-neutral-700 transition-colors min-h-[44px]'

export function SwipeCard({ poem, preview, onSkip, onOpen }: Props) {
  function stop(e: MouseEvent) {
    e.stopPropagation()
  }

  return (
    <div
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen()
        }
      }}
      className="absolute inset-0 rounded-2xl bg-[#F4ECC8] shadow-md cursor-pointer flex flex-col px-8 pt-9 pb-6 overflow-hidden"
      style={{ zIndex: 2 }}
    >
      {/* Title */}
      <p className="font-serif text-[1.125rem] leading-[1.3] font-bold text-[#999] mb-5">
        {poem.title}
      </p>

      {/* Preview */}
      <div className="mt-auto mb-6">
        <p className="font-serif text-[1.125rem] leading-[1.85] text-[#111] whitespace-pre-wrap">
          {preview}
        </p>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2.5" onClick={stop}>
        <button
          type="button"
          onClick={onSkip}
          className={actionBtn}
          aria-label="Skip"
        >
          skip
        </button>
        <button
          type="button"
          onClick={onOpen}
          className={actionBtn}
          aria-label="Read"
        >
          read
        </button>
      </div>
    </div>
  )
}
