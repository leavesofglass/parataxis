import Link from 'next/link'
import { Masthead } from '../components/Masthead'
import { LibraryBadge } from '../components/LibraryBadge'

export const metadata = { title: 'About · parataxis' }

export default function AboutPage() {
  return (
    <main className="h-dvh flex flex-col bg-[#FAF6E9]">
      {/* Row 1: back (left) · library (right) — matches home page */}
      <div className="w-full flex items-center justify-between px-6 pt-8 shrink-0">
        <Link
          href="/"
          className="text-[10px] font-sans tracking-[0.18em] text-neutral-300 uppercase hover:text-neutral-500 transition-colors"
        >
          ← Back
        </Link>
        <LibraryBadge />
      </div>

      {/* Row 2: masthead — same size/position as home page */}
      <div className="flex justify-center pt-4 pb-3 shrink-0">
        <Masthead />
      </div>

      {/* Content — card matches the home swipe-card visual (bg, radius, shadow,
          padding) but is content-sized rather than aspect-locked. Width mirrors
          the home card's mobile/desktop caps (drops the height-bounded branch
          since the about copy is short). */}
      <div className="flex justify-center px-6" style={{ paddingTop: 'calc(33dvh - 100px)' }}>
        <div
          className="rounded-2xl bg-[#F4ECC8] shadow-md px-8 pt-9 pb-9"
          style={{ width: 'min(80vw, 360px)' }}
        >
          <p className="font-serif text-[1rem] leading-[1.85] text-neutral-600">
            <strong className="font-semibold text-[#111]">parataxis</strong>
            {' '}(n.) the placing of clauses, images, or lines side by side, without making
            one subordinate to another. A poetry discovery app. Made by{' '}
            <a
              href="https://instagram.com/matthewsiegel"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#111] underline underline-offset-2 decoration-neutral-300 hover:decoration-neutral-500 transition-colors"
            >
              Matthew Siegel
            </a>
            {' '}in Brooklyn.
          </p>
        </div>
      </div>
    </main>
  )
}
