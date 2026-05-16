import Link from 'next/link'
import { Masthead } from '../components/Masthead'

export const metadata = { title: 'About · parataxis' }

export default function AboutPage() {
  return (
    <main className="h-dvh flex flex-col bg-[#FAF6E9]">
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

      {/* Content — padding-top places paragraph ~⅓ down the page */}
      <div className="px-8" style={{ paddingTop: 'calc(33dvh - 80px)' }}>
        <p className="font-serif text-[1rem] leading-[1.85] text-neutral-600 max-w-sm">
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
    </main>
  )
}
