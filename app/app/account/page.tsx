'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { getSupabase } from '@/lib/supabase'
import { sendSignInLink } from '@/lib/authActions'
import { Masthead } from '@/app/components/Masthead'
import type { User } from '@supabase/supabase-js'

type SentMode = 'confirm' | 'magic' | null

export default function AccountPage() {
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const [email, setEmail] = useState('')
  const [sending, setSending] = useState(false)
  const [sentMode, setSentMode] = useState<SentMode>(null)
  const [sendError, setSendError] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('error')) {
      setAuthError('Sign-in link expired or invalid. Please request a new one.')
    }

    getSupabase()
      .auth.getUser()
      .then(({ data }: { data: { user: User | null } }) => {
        setUser(data.user)
        setReady(true)
      })
  }, [])

  const redirectTo = typeof window !== 'undefined'
    ? `${window.location.origin}/auth/callback`
    : '/auth/callback'

  async function handleSendLink(e: React.FormEvent) {
    e.preventDefault()
    setSending(true)
    setSendError(null)

    const result = await sendSignInLink(email, redirectTo)
    setSending(false)

    if (result.ok) {
      setSentMode(result.mode)
    } else {
      setSendError(result.error)
    }
  }

  async function handleSignOut() {
    const supabase = getSupabase()
    await supabase.auth.signOut()
    await supabase.auth.signInAnonymously()
    router.push('/')
  }

  if (!ready) {
    return (
      <main className="h-dvh flex items-center justify-center bg-[#F4ECC8]">
        <span className="text-sm font-sans text-neutral-300 tracking-widest">·  ·  ·</span>
      </main>
    )
  }

  const isAnonymous = !user?.email

  return (
    <main className="h-dvh flex flex-col bg-[#F4ECC8]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-12 pb-4 shrink-0">
        <Link
          href="/"
          className="text-[10px] font-sans tracking-[0.18em] text-neutral-300 uppercase hover:text-neutral-500 transition-colors"
        >
          ← Back
        </Link>
        <Masthead />
        <span className="w-10" />
      </div>

      <div className="flex-1 flex flex-col px-8 pt-10">
        {authError && (
          <p className="font-sans text-[0.8rem] text-red-400 mb-6">{authError}</p>
        )}

        {isAnonymous ? (
          <>
            <p className="font-serif text-[1rem] leading-[1.7] text-neutral-400 mb-8">
              You&apos;re browsing anonymously.
            </p>

            {sentMode === 'confirm' && (
              <p className="font-sans text-[0.85rem] leading-[1.6] text-neutral-500">
                Check your email — click the link to confirm{' '}
                <span className="text-[#111]">{email}</span> and save your library.
              </p>
            )}
            {sentMode === 'magic' && (
              <p className="font-sans text-[0.85rem] leading-[1.6] text-neutral-500">
                Check your email — we sent a sign-in link to{' '}
                <span className="text-[#111]">{email}</span>.
              </p>
            )}

            {!sentMode && (
              <form onSubmit={handleSendLink} className="flex flex-col gap-3">
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
                {sendError && (
                  <p className="font-sans text-[0.75rem] text-red-400">{sendError}</p>
                )}
              </form>
            )}
          </>
        ) : (
          <>
            <p className="font-sans text-[0.7rem] tracking-[0.14em] text-neutral-400 uppercase mb-1.5">
              Signed in as
            </p>
            <p className="font-serif text-[1.1rem] text-[#111] mb-10 break-all">
              {user.email}
            </p>
            <button
              onClick={handleSignOut}
              className="self-start py-2.5 px-6 border border-neutral-200 rounded-full font-sans text-[0.8rem] text-neutral-400 hover:border-neutral-400 hover:text-neutral-600 transition-colors"
            >
              Sign out
            </button>
          </>
        )}
      </div>
    </main>
  )
}
