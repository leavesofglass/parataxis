import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import Link from 'next/link'
import { getSupabaseServer } from '@/lib/supabaseServer'
import { ShareButton } from '@/app/components/ShareButton'
import { sanitizePoemHtml } from '@/lib/sanitize'

interface PoemRow {
  id: string
  title: string
  author: string
  body: string
  body_html: string | null
}

// Origin used for absolute URLs in OG/Twitter metadata. Falls back to the
// Vercel deploy URL, then localhost for local dev. Override with
// NEXT_PUBLIC_SITE_URL in prod once a stable hostname is wired up.
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'http://localhost:3000')

async function fetchPoem(id: string): Promise<PoemRow | null> {
  const supabase = getSupabaseServer()
  const { data, error } = await supabase
    .from('poems')
    .select('id, title, author, body, body_html')
    .eq('id', id)
    .maybeSingle()
  if (error || !data) return null
  return data as PoemRow
}

// Builds a ~160-char description from the first non-blank lines of the body,
// preferring whole-word truncation for readability in social cards.
function makeDescription(body: string, maxLen = 160): string {
  const lines = body.split('\n').filter((l) => l.trim() !== '').slice(0, 2)
  const joined = lines.join(' / ').replace(/\s+/g, ' ').trim()
  if (joined.length <= maxLen) return joined
  return joined.slice(0, maxLen - 1).replace(/\s+\S*$/, '') + '…'
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>
}): Promise<Metadata> {
  const { id } = await params
  const poem = await fetchPoem(id)
  if (!poem) return { title: 'Poem not found · sheaf' }

  const title = `${poem.title} — ${poem.author} · sheaf`
  const description = makeDescription(poem.body)
  const url = `${SITE_URL}/p/${poem.id}`
  const image = `${SITE_URL}/sheaf-logo.png`

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url,
      type: 'article',
      images: [{ url: image }],
    },
    twitter: {
      card: 'summary',
      title,
      description,
      images: [image],
    },
  }
}

export default async function PoemPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const poem = await fetchPoem(id)
  if (!poem) notFound()

  return (
    <main className="h-dvh overflow-y-auto overscroll-contain bg-[#ECECEC]">
      <div className="min-h-full flex flex-col">
        {/* Header — back link (left), share (right). Share is wrapped in the
            same height frame as the in-modal share so visual weight matches. */}
        <header className="flex items-center justify-between px-6 pt-8 pb-2 shrink-0 border-b border-[rgba(0,0,0,0.08)]">
          <Link
            href="/"
            className="text-[10px] leading-none font-sans tracking-[0.18em] text-neutral-400 uppercase hover:text-neutral-600 transition-colors"
          >
            ← sheaf
          </Link>
          <div className="h-[1.4rem] inline-flex items-center">
            <ShareButton poemId={poem.id} title={poem.title} author={poem.author} />
          </div>
        </header>

        {/* Poem */}
        <article className="flex-1 w-full max-w-xl mx-auto px-8 pt-8 pb-12">
          <h1 className="font-serif text-[1.5rem] leading-[1.35] font-normal text-[#111] mb-10">
            {poem.title}
          </h1>
          <div className="font-serif text-[1.05rem] leading-[1.4] text-[#111]">
            {(poem.body_html ?? poem.body).replace(/^(?:[ \t]*\n)+/, '').split('\n').map((line, i) =>
              line.trim()
                ? poem.body_html != null
                  ? <span key={i} className="poem-line" dangerouslySetInnerHTML={{ __html: sanitizePoemHtml(line) }} />
                  : <span key={i} className="poem-line">{line}</span>
                : <span key={i} aria-hidden="true" className="block h-[0.6em]" />
            )}
          </div>
          <p className="font-sans text-[0.9rem] italic text-neutral-400 mt-10 mb-2">
            {poem.author}
          </p>
        </article>

        {/* Footer */}
        <div className="px-6 py-10 text-center shrink-0">
          <Link
            href="/"
            className="text-[0.75rem] font-sans tracking-[0.14em] uppercase text-neutral-400 hover:text-neutral-600 transition-colors"
          >
            Discover more poems →
          </Link>
        </div>
      </div>
    </main>
  )
}
