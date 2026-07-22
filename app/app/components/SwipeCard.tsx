'use client'

import type { Poem } from '../types'

interface Props {
  poem: Poem
  preview: string
  onOpen: () => void
}

export function SwipeCard({ poem, preview, onOpen }: Props) {
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
      className="absolute inset-0 rounded-2xl bg-[#ECECEC] shadow-md cursor-pointer flex flex-col px-8 pt-9 pb-9 overflow-hidden"
      style={{ zIndex: 2 }}
    >
      {/* Title */}
      <p className="font-serif text-[1.125rem] leading-[1.3] font-bold text-[#999] mb-5">
        {poem.title}
      </p>

      {/* Preview */}
      <div className="mt-auto">
        <p className="font-serif text-[1.125rem] leading-[1.85] text-[#111] whitespace-pre-wrap">
          {preview}
        </p>
      </div>
    </div>
  )
}
