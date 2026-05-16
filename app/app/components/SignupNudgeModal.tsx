'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { sendSignInLink } from '@/lib/authActions'

type Threshold = 1 | 5 | 10

interface Props {
  threshold: Threshold
  onDismiss: () => void
}

const COPY: Record<Threshold, { title: string; body: string }> = {
  1: {
    title: 'Save your library',
    body: "You're browsing anonymously. Add your email and we'll remember your poems on any device.",
  },
  5: {
    title: "Don't lose your library",
    body: "You've saved a few poems now. Add your email to keep them safe across devices.",
  },
  10: {
    title: 'One more reminder',
    body: "Your library is building up. Add your email so you don't lose these poems if you clear your browser.",
  },
}

export function SignupNudgeModal({ threshold, onDismiss }: Props) {
  const [email, setEmail] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [sentEmail, setSentEmail] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { title, body } = COPY[threshold]
  const redirectTo = typeof window !== 'undefined'
    ? `${window.location.origin}/auth/callback`
    : '/auth/callback'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSending(true)
    setError(null)

    const result = await sendSignInLink(email, redirectTo)
    setSending(false)

    if (result.ok) {
      setSentEmail(email)
      setSent(true)
      setTimeout(onDismiss, 2200)
    } else {
      setError(result.error)
    }
  }

  return (
    // Backdrop — click outside to dismiss
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      onClick={onDismiss}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 px-6"
    >
      {/* Panel — stop propagation so clicks inside don't dismiss */}
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 10 }}
        transition={{ type: 'spring', damping: 28, stiffness: 320 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm bg-[#faf9f7] rounded-2xl shadow-lg px-7 pt-8 pb-7 flex flex-col"
      >
        {sent ? (
          <div className="py-3 text-center">
            <p className="font-serif text-[1.1rem] text-[#111] mb-2">Check your email.</p>
            <p className="font-sans text-[0.82rem] leading-[1.6] text-neutral-400">
              We sent a link to{' '}
              <span className="text-[#111]">{sentEmail}</span>.
            </p>
          </div>
        ) : (
          <>
            <h2 className="font-serif text-[1.25rem] leading-[1.3] font-normal text-[#111] mb-3">
              {title}
            </h2>
            <p className="font-sans text-[0.82rem] leading-[1.65] text-neutral-400 mb-6">
              {body}
            </p>

            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <input
                type="email"
                required
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border border-neutral-200 rounded-xl px-4 py-3 font-sans text-[0.9rem] text-[#111] bg-white placeholder:text-neutral-300 focus:outline-none focus:border-neutral-400 transition-colors"
              />
              <button
                type="submit"
                disabled={sending}
                className="w-full py-3 bg-[#111] text-white rounded-xl font-sans text-[0.8rem] font-medium tracking-wide disabled:opacity-40 hover:bg-neutral-700 transition-colors"
              >
                {sending ? '…' : 'Send sign-in link'}
              </button>
              {error && (
                <p className="font-sans text-[0.75rem] text-red-400">{error}</p>
              )}
            </form>

            <button
              onClick={onDismiss}
              className="mt-5 self-center font-sans text-[0.75rem] text-neutral-300 hover:text-neutral-500 transition-colors"
            >
              Maybe later
            </button>
          </>
        )}
      </motion.div>
    </motion.div>
  )
}
