import Link from 'next/link'
import { LibraryList } from '../components/LibraryList'

export const metadata = { title: 'Library · parataxis' }

export default function LibraryPage() {
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
          Library
        </span>
        <span className="w-10" /> {/* spacer to centre the title */}
      </div>

      <LibraryList />
    </main>
  )
}
