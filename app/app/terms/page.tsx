import Link from 'next/link'
import { Masthead } from '@/app/components/Masthead'

export const metadata = { title: 'Terms — sheaf' }

export default function TermsPage() {
  return (
    <main className="min-h-dvh flex flex-col bg-[#ECECEC]">
      <div className="flex items-center justify-between px-6 pt-12 pb-4 shrink-0 border-b border-[rgba(0,0,0,0.08)]">
        <Link
          href="/account"
          className="text-[10px] font-sans tracking-[0.18em] text-neutral-300 uppercase hover:text-neutral-500 transition-colors"
        >
          ← Back
        </Link>
        <Masthead />
        <div className="w-10" />
      </div>

      <div className="flex-1 px-8 pt-10 pb-16 max-w-prose">
        <h1 className="font-sans text-[0.7rem] tracking-[0.14em] text-neutral-400 uppercase mb-8">
          Terms of use
        </h1>

        <div className="flex flex-col gap-6 font-sans text-[0.85rem] leading-[1.7] text-neutral-500">
          <div>
            <p className="text-[#111] mb-1">What sheaf is</p>
            <p>
              sheaf is a personal poetry reading app. It shows you poems and
              learns your taste over time based on how you respond to them.
            </p>
          </div>

          <div>
            <p className="text-[#111] mb-1">The poems</p>
            <p>
              Poems are sourced from public-domain collections and contemporary
              poetry publishers who make work available online. sheaf is a
              non-commercial project. If you are a rights holder with a concern
              about a specific poem, please get in touch.
            </p>
          </div>

          <div>
            <p className="text-[#111] mb-1">Your account</p>
            <p>
              You can use sheaf anonymously without signing in. If you sign in
              with an email address, your library and preferences are saved to
              your account. You can request deletion of your account at any time.
            </p>
          </div>

          <div>
            <p className="text-[#111] mb-1">Availability</p>
            <p>
              sheaf is provided as-is. There are no guarantees of uptime,
              permanence, or fitness for any particular purpose.
            </p>
          </div>

          <div>
            <p className="text-[#111] mb-1">Contact</p>
            <p>
              <a
                href="mailto:sheaf.me@gmail.com"
                className="underline underline-offset-2 hover:text-neutral-700 transition-colors"
              >
                sheaf.me@gmail.com
              </a>
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
