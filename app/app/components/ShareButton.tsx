'use client'

import { useState } from 'react'

interface Props {
  poemId: string
  title: string
  author: string
  className?: string
}

type Status = 'idle' | 'copied' | 'shared'

export function ShareButton({ poemId, title, author, className = '' }: Props) {
  const [status, setStatus] = useState<Status>('idle')

  function flash(s: Status) {
    setStatus(s)
    setTimeout(() => setStatus('idle'), 1800)
  }

  async function handleShare() {
    const url = `${window.location.origin}/p/${poemId}`
    const shareTitle = `${title} by ${author} — parataxis`

    if (typeof navigator !== 'undefined' && navigator.share) {
      try {
        await navigator.share({ title: shareTitle, url })
        flash('shared')
        return
      } catch (err) {
        // User-cancelled share is not a failure — stay silent.
        if ((err as Error).name === 'AbortError') return
        // Real error → fall through to clipboard.
      }
    }

    try {
      await navigator.clipboard.writeText(url)
      flash('copied')
    } catch {
      // No reliable surface for the failure here; better to no-op than to
      // show a misleading "Copied" toast.
    }
  }

  return (
    <button
      type="button"
      onClick={handleShare}
      aria-label="Share poem"
      className={`relative inline-flex items-center justify-center text-neutral-500 hover:text-neutral-700 transition-colors ${className}`}
    >
      {/* Three-node share glyph (Lucide Share2 geometry, inlined to avoid a deps add) */}
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="18" cy="5" r="3" />
        <circle cx="6" cy="12" r="3" />
        <circle cx="18" cy="19" r="3" />
        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
        <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
      </svg>

      {status !== 'idle' && (
        <span
          aria-live="polite"
          className="absolute right-full top-1/2 -translate-y-1/2 mr-2 text-[10px] font-sans tracking-[0.14em] uppercase text-neutral-400 whitespace-nowrap pointer-events-none"
        >
          {status === 'copied' ? 'Copied' : 'Shared'}
        </span>
      )}
    </button>
  )
}
