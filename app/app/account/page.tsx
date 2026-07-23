'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

const LEGAL_LINKS = (
  <p className="font-sans text-[0.7rem] text-neutral-300 mt-8">
    <Link href="/privacy" className="hover:text-neutral-500 transition-colors">Privacy</Link>
    <span className="mx-2">·</span>
    <Link href="/terms" className="hover:text-neutral-500 transition-colors">Terms</Link>
  </p>
)
import { getSupabase } from '@/lib/supabase'
import { sendSignInLink, signInWithGoogle } from '@/lib/authActions'
import { Masthead } from '@/app/components/Masthead'
import { LibraryBadge } from '@/app/components/LibraryBadge'
import type { User } from '@supabase/supabase-js'

type SentMode = 'confirm' | 'magic' | null

const BUCKETS_KEY = 'parataxis_length_buckets'
type LengthBuckets = { short: boolean; medium: boolean; long: boolean }
const DEFAULT_BUCKETS: LengthBuckets = { short: true, medium: true, long: true }
const BUCKET_OPTIONS: { key: keyof LengthBuckets; label: string }[] = [
  { key: 'short',  label: 'Short  (≤ 14 lines)' },
  { key: 'medium', label: 'Medium (15 – 40 lines)' },
  { key: 'long',   label: 'Long   (41 + lines)' },
]

export default function AccountPage() {
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const [email, setEmail] = useState('')
  const [sending, setSending] = useState(false)
  const [sentMode, setSentMode] = useState<SentMode>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [googleError, setGoogleError] = useState<string | null>(null)

  const [buckets, setBuckets] = useState<LengthBuckets>(DEFAULT_BUCKETS)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('error')) {
      setAuthError('Sign-in link expired or invalid. Please request a new one.')
    }

    try {
      const v = localStorage.getItem(BUCKETS_KEY)
      if (v) {
        const parsed = JSON.parse(v)
        if (parsed && typeof parsed === 'object') {
          setBuckets({
            short:  parsed.short  !== false,
            medium: parsed.medium !== false,
            long:   parsed.long   !== false,
          })
        }
      }
    } catch {}

    getSupabase()
      .auth.getUser()
      .then(({ data }: { data: { user: User | null } }) => {
        setUser(data.user)
        setReady(true)
      })
  }, [])

  function toggleBucket(key: keyof LengthBuckets) {
    setBuckets((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      try { localStorage.setItem(BUCKETS_KEY, JSON.stringify(next)) } catch {}
      return next
    })
  }

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

  async function handleSignInWithGoogle() {
    setGoogleLoading(true)
    setGoogleError(null)
    const { error } = await signInWithGoogle(redirectTo)
    if (error) {
      setGoogleError(error)
      setGoogleLoading(false)
    }
    // on success the browser redirects away — no cleanup needed
  }

  async function handleSignOut() {
    const supabase = getSupabase()
    await supabase.auth.signOut()
    await supabase.auth.signInAnonymously()
    router.push('/')
  }

  if (!ready) {
    return (
      <main className="h-dvh flex items-center justify-center bg-[#ECECEC]">
        <span className="text-sm font-sans text-neutral-300 tracking-widest">·  ·  ·</span>
      </main>
    )
  }

  const isAnonymous = !user?.email

  return (
    <main className="h-dvh flex flex-col bg-[#ECECEC]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-12 pb-4 shrink-0 border-b border-[rgba(0,0,0,0.08)]">
        <Link
          href="/"
          className="text-[10px] font-sans tracking-[0.18em] text-neutral-300 uppercase hover:text-neutral-500 transition-colors"
        >
          ← Back
        </Link>
        <Masthead />
        <LibraryBadge />
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
              <div className="flex flex-col gap-3">
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

                <div className="flex items-center gap-3">
                  <div className="flex-1 h-px bg-neutral-200" />
                  <span className="font-sans text-[0.7rem] text-neutral-300 tracking-wide">or</span>
                  <div className="flex-1 h-px bg-neutral-200" />
                </div>

                <button
                  type="button"
                  onClick={handleSignInWithGoogle}
                  disabled={googleLoading}
                  className="w-full py-3 bg-white border border-[#dadce0] rounded-xl font-sans text-[0.8rem] font-medium text-[#3c4043] hover:bg-[#f8f9fa] hover:border-[#c6c6c6] transition-colors disabled:opacity-50 flex items-center justify-center gap-2.5 shadow-sm"
                >
                  {googleLoading ? (
                    <span className="text-[#3c4043]">…</span>
                  ) : (
                    <>
                      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                      </svg>
                      Sign in with Google
                    </>
                  )}
                </button>
                {googleError && (
                  <p className="font-sans text-[0.75rem] text-red-400">{googleError}</p>
                )}
              </div>
            )}
            {LEGAL_LINKS}
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

        <section className="mt-12 border-t border-neutral-200 pt-8">
          <p className="font-sans text-[0.7rem] tracking-[0.14em] text-neutral-400 uppercase mb-4">
            Reading preferences
          </p>
          <p className="font-sans text-[0.75rem] text-neutral-400 mb-3">Poem length</p>
          <div className="flex flex-col gap-2">
            {BUCKET_OPTIONS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => toggleBucket(key)}
                aria-pressed={buckets[key]}
                className={`text-left py-2.5 px-5 border rounded-full font-sans text-[0.8rem] transition-colors ${
                  buckets[key]
                    ? 'border-[#111] text-[#111]'
                    : 'border-neutral-200 text-neutral-400 hover:border-neutral-400 hover:text-neutral-600'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {LEGAL_LINKS}
        </section>
      </div>
    </main>
  )
}
