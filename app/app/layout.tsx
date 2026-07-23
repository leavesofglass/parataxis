import type { Metadata } from 'next'
import { Inter, Spectral } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const spectral = Spectral({
  subsets: ['latin'],
  variable: '--font-spectral',
  style: ['normal', 'italic'],
  weight: ['400', '500', '600'],
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'sheaf',
  description: 'A poetry discovery app',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${spectral.variable} h-full`}>
      <body className="h-full antialiased">{children}</body>
    </html>
  )
}
