import Link from 'next/link'

interface Props {
  href?: string
}

export function Masthead({ href: _href }: Props) {
  return (
    <Link
      href="/"
      className="font-masthead text-[22px] sm:text-[15px] tracking-[0.15em] text-black/35 hover:text-black/55 transition-colors"
    >
      sheaf
    </Link>
  )
}
