interface Props {
  // href kept in the interface for call-site compatibility; no longer used
  href?: string
}

export function Masthead({ href: _href }: Props) {
  return (
    <span
      className="font-masthead text-[22px] sm:text-[15px] tracking-[0.15em] text-black/35"
    >
      Sheaf
    </span>
  )
}
