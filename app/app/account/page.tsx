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
import { sendSignInLink } from '@/lib/authActions'
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
