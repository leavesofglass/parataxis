import Link from 'next/link'

interface Props {
  href?: string
}

export function Masthead({ href = '/about' }: Props) {
  return (
    <Link
      href={href}
      className="font-masthead text-[15px] tracking-[0.15em] text-black/35 hover:text-black/50 transition-colors"
    >
      parataxis
    </Link>
  )
}
