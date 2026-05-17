import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const migrateFrom = searchParams.get('migrate_from')

  if (code) {
    const cookieStore = await cookies()
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll() {
            return cookieStore.getAll()
          },
          setAll(cookiesToSet) {
            try {
              cookiesToSet.forEach(({ name, value, options }) =>
                cookieStore.set(name, value, options)
              )
            } catch {
              // Guards against unexpected read-only contexts during SSG.
            }
          },
        },
      }
    )

    const { error: sessionError } = await supabase.auth.exchangeCodeForSession(code)

    if (!sessionError) {
      // If the user now has an email (magic-link sign-in OR email confirmation
      // from updateUser), mark their profile as no longer anonymous.
      const { data: { user } } = await supabase.auth.getUser()
      if (user?.email) {
        await supabase
          .from('profiles')
          .update({ is_anonymous: false })
          .eq('id', user.id)
        // Ignore update errors — best-effort; doesn't affect the user flow.
      }

      if (migrateFrom) {
        // TODO: interactions orphaned by sign-ins before this fix shipped are
        // not recoverable here — their anon user_ids aren't in any future
        // magic-link URL.
        const { error: migrateError } = await supabase.rpc(
          'migrate_anon_interactions',
          { anon_user_id: migrateFrom },
        )
        if (migrateError) {
          console.error('migrate_anon_interactions failed:', migrateError)
        }
      }

      return NextResponse.redirect(`${origin}/`)
    }
  }

  return NextResponse.redirect(`${origin}/account?error=auth_failed`)
}
