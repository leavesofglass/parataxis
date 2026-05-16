'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { getSupabase } from '@/lib/supabase'
import type { User } from '@supabase/supabase-js'

// Sent mode distinguishes "confirm your new email" from "here's a magic link"
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
  // True when updateUser returned email_exists — offer signInWithOtp instead
  const [emailInUse, setEmailInUse] = useState(false)

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

  // Called when anonymous user submits the email form.
  // Tries to attach the email to their existing user_id via updateUser.
  // Falls back to signInWithOtp on email_exists (returning user, different device).
  async function handleAttachOrSignIn(e: React.FormEvent) {
    e.preventDefault()
    setSending(true)
    setSendError(null)
    setEmailInUse(false)

    const supabase = getSupabase()

    if (user?.is_anonymous === true) {
      // Attach email to current anonymous user_id
      const { error } = await supabase.auth.updateUser(
        { email },
        { emailRedirectTo: redirectTo }
      )

      setSending(false)

      if (!error) {
        setSentMode('confirm')
        return
      }

      if (error.code === 'email_exists') {
        // Email belongs to a different account — offer magic-link sign-in
        setEmailInUse(true)
        return
      }

      setSendError(error.message)
      return
    }

    // No anonymous session (edge case) — just send a magic link
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: redirectTo },
    })
    setSending(false)
    if (error) setSendError(error.message)
    else setSentMode('magic')
  }

  // Called from the "Send sign-in link" fallback when email is already in use.
  // Sign out the anonymous session first so the PKCE challenge is initiated
  // without an active user — otherwise the exchange binds to the anonymous
  // user_id instead of signing into the existing email-linked account.
  async function handleSignInFallback() {
    setSending(true)
    setSendError(null)

    await getSupabase().auth.signOut()

    const { error } = await getSupabase().auth.signInWithOtp({
      email,
      options: { emailRedirectTo: redirectTo },
    })
    setSending(false)

    if (error) {
      setSendError(error.message)
    } else {
      setEmailInUse(false)
      setSentMode('magic')
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
      <main className="h-dvh flex items-center justify-center bg-[#faf9f7]">
        <span className="text-sm font-sans text-neutral-300 tracking-widest">·  ·  ·</span>
      </main>
    )
  }

  const isAnonymous = !user?.email

  return (
    <main className="h-dvh flex flex-col bg-[#faf9f7]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-12 pb-4 shrink-0">
        <Link
          href="/"
          className="text-[10px] font-sans tracking-[0.18em] text-neutral-300 uppercase hover:text-neutral-500 transition-colors"
        >
          ← Back
        </Link>
        <span className="text-[10px] font-sans tracking-[0.2em] text-neutral-400 uppercase">
          Account
        </span>
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

            {/* ── Sent states ───────────────────────────────── */}
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

            {/* ── Email already in use ──────────────────────── */}
            {!sentMode && emailInUse && (
              <div className="flex flex-col gap-3">
                <p className="font-sans text-[0.85rem] leading-[1.6] text-neutral-500">
                  That email is already linked to an account.
                </p>
                <button
                  onClick={handleSignInFallback}
                  disabled={sending}
                  className="w-full py-3 bg-[#111] text-white rounded-xl font-sans text-[0.8rem] font-medium tracking-wide disabled:opacity-40 hover:bg-neutral-700 transition-colors"
                >
                  {sending ? '…' : 'Send sign-in link'}
                </button>
                <button
                  onClick={() => { setEmailInUse(false); setEmail('') }}
                  className="font-sans text-[0.75rem] text-neutral-300 hover:text-neutral-500 transition-colors text-center"
                >
                  Use a different email
                </button>
                {sendError && (
                  <p className="font-sans text-[0.75rem] text-red-400">{sendError}</p>
                )}
              </div>
            )}

            {/* ── Email form ────────────────────────────────── */}
            {!sentMode && !emailInUse && (
              <form onSubmit={handleAttachOrSignIn} className="flex flex-col gap-3">
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
