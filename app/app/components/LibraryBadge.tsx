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
      className="flex items-center gap-1 hover:opacity-70 transition-opacity"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/sheaf-logo.png" alt="Sheaf" width={40} height={40}
           style={{ objectFit: 'contain' }} className="block" />
      {count > 0 && (
        <span className="text-[10px] font-sans tracking-wide tabular-nums text-neutral-400">
          {count}
        </span>
      )}
    </Link>
  )
}
