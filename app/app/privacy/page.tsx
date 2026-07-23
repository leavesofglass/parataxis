import Link from 'next/link'
import { Masthead } from '@/app/components/Masthead'

export const metadata = { title: 'Privacy — sheaf' }

export default function PrivacyPage() {
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
          Privacy
        </h1>

        <div className="flex flex-col gap-6 font-sans text-[0.85rem] leading-[1.7] text-neutral-500">
          <div>
            <p className="text-[#111] mb-1">What sheaf stores</p>
            <p>
              When you sign in, we store your email address. As you use the app,
              we record which poems you save, like, dislike, or skip. That record
              is what powers your personal recommendations and your saved library.
            </p>
          </div>

          <div>
            <p className="text-[#111] mb-1">Who can see it</p>
            <p>
              You can see your library inside the app. As the operator of sheaf,
              I can also see this data in the database.
            </p>
          </div>

          <div>
            <p className="text-[#111] mb-1">Third parties</p>
            <p>
              Authentication and the database are hosted by{' '}
              <a
                href="https://supabase.com"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-2 hover:text-neutral-700 transition-colors"
              >
                Supabase
              </a>
              . No data is sold, shared with advertisers, or given to any other
              third party.
            </p>
          </div>

          <div>
            <p className="text-[#111] mb-1">Deletion</p>
            <p>
              To delete your account and all associated data, contact us at the
              address below.
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
