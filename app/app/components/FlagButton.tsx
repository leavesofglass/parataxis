'use client'

import { useState } from 'react'
import { getSupabase } from '../../lib/supabase'

const REASONS = [
  'Formatting problem',
  'Wrong or missing text',
  'Request removal',
] as const

type State = 'idle' | 'open' | 'submitting' | 'done'

export function FlagButton({ poemId }: { poemId: string }) {
  const [state, setState] = useState<State>('idle')
  const [reason, setReason] = useState<string | null>(null)
  const [note, setNote] = useState('')

  async function submit() {
    if (!reason) return
    setState('submitting')
    const supabase = getSupabase()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) { setState('open'); return }
    await supabase.from('poem_flags').insert({
      poem_id: poemId,
      reason,
      note: note.trim() || null,
      user_id: user.id,
    })
    setState('done')
  }

  if (state === 'done') {
    return (
      <p className="font-sans text-[0.78rem] text-neutral-400 mt-3">
        Noted. Thank you.
      </p>
    )
  }

  if (state === 'idle') {
    return (
      <button
        type="button"
        onClick={() => setState('open')}
        aria-label="Flag a problem with this poem"
        className="mt-3 inline-flex items-center justify-center text-neutral-300 hover:text-neutral-400 transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
          <line x1="4" y1="22" x2="4" y2="15" />
        </svg>
      </button>
    )
  }

  return (
    <div className="mt-3 space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {REASONS.map(r => (
          <button
            key={r}
            type="button"
            onClick={() => setReason(r === reason ? null : r)}
            className={`px-2.5 py-1 rounded-full text-[0.72rem] font-sans border transition-colors
              ${reason === r
                ? 'border-neutral-500 text-neutral-600 bg-neutral-100'
                : 'border-neutral-300 text-neutral-400 hover:border-neutral-400 hover:text-neutral-500'
              }`}
          >
            {r}
          </button>
        ))}
      </div>

      <input
        type="text"
        placeholder="Optional note"
        value={note}
        onChange={e => setNote(e.target.value)}
        maxLength={200}
        className="w-full bg-transparent border-b border-neutral-200 text-[0.78rem] font-sans text-neutral-500 placeholder:text-neutral-300 focus:outline-none focus:border-neutral-400 py-0.5"
      />

      <div className="flex gap-3 items-center">
        <button
          type="button"
          onClick={submit}
          disabled={!reason || state === 'submitting'}
          className="text-[0.72rem] font-sans text-neutral-500 hover:text-neutral-700 disabled:text-neutral-300 transition-colors"
        >
          Send
        </button>
        <button
          type="button"
          onClick={() => { setState('idle'); setReason(null); setNote('') }}
          className="text-[0.72rem] font-sans text-neutral-300 hover:text-neutral-400 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
