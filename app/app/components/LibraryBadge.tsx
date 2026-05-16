'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { getSupabase } from '@/lib/supabase'
import { fetchSavedCount } from '@/lib/library'

export function LibraryBadge() {
  const [count, setCount] = useState(0)

  useEffect(() => {
    getSupabase()
      .auth.getUser()
      .then(({ data: { user } }) => {
        if (user) fetchSavedCount(user.id).then(setCount)
      })
  }, [])

  return (
    <Link
      href="/library"
      aria-label="Library"
      className="flex items-center gap-1 hover:opacity-70 transition-opacity"
    >
      <span className="text-[1.25rem] leading-none">📚</span>
      {count > 0 && (
        <span className="text-[10px] font-sans tracking-wide tabular-nums text-neutral-400">
          {count}
        </span>
      )}
    </Link>
  )
}
