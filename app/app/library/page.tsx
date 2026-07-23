import Link from 'next/link'
import { LibraryList } from '../components/LibraryList'
import { Masthead } from '../components/Masthead'
import { LibraryBadge } from '../components/LibraryBadge'

export const metadata = { title: 'Library · sheaf' }

export default function LibraryPage() {
  return (
    <main className="h-dvh flex flex-col bg-[#ECECEC]">
      <div className="w-full flex items-center px-6 pt-3 pb-1 shrink-0 border-b border-[rgba(0,0,0,0.08)]">
        <div className="flex-1 flex items-center h-10">
          <Link
            href="/"
            className="text-[10px] font-sans tracking-[0.18em] text-neutral-300 uppercase hover:text-neutral-500 transition-colors"
          >
            ← Back
          </Link>
        </div>
        <Masthead />
        <div className="flex-1 flex items-center justify-end h-10">
          <LibraryBadge />
        </div>
      </div>

      <LibraryList />
    </main>
  )
}
