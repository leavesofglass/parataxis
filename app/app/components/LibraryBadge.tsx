'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { getSupabase } from '@/lib/supabase'
import { fetchSavedCount } from '@/lib/library'
import type { User } from '@supabase/supabase-js'

export function LibraryBadge() {
  const [count, setCount] = useState(0)

  useEffect(() => {
    getSupabase()
      .auth.getUser()
      .then(({ data }: { data: { user: User | null } }) => {
        if (data.user) fetchSavedCount(data.user.id).then(setCount)
      })
  }, [])

  return (
    <Link
      href="/library"
      aria-label="Library"
      className="flex items-center gap-1.5 text-neutral-500 hover:text-neutral-700 transition-colors"
    >
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
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
      </svg>
      {count > 0 && (
        <span className="text-[10px] leading-none font-sans tracking-wide tabular-nums text-neutral-400">
          {count}
        </span>
      )}
    </Link>
  )
}
