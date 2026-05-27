import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

const MIGRATE_COOKIE = 'anon_user_id_for_migration'

export async function GET(request: Request) {
  console.log('[auth/callback] request URL:', request.url)
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')

  if (code) {
    const cookieStore = await cookies()
    const migrateFrom = cookieStore.get(MIGRATE_COOKIE)?.value ?? null
    console.log(
      `[auth/callback] ${MIGRATE_COOKIE} cookie:`,
      migrateFrom === null ? 'absent' : `present="${migrateFrom}"`,
    )

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
        console.log('[auth/callback] calling migrate_anon_interactions for anon_user_id:', migrateFrom)
        const { data: migrateData, error: migrateError } = await supabase.rpc(
          'migrate_anon_interactions',
          { anon_user_id: migrateFrom },
        )
        if (migrateError) {
          console.error('[auth/callback] migrate_anon_interactions failed:', migrateError)
        } else {
          console.log('[auth/callback] migrate_anon_interactions result:', migrateData)
        }
        cookieStore.delete(MIGRATE_COOKIE)
        console.log(`[auth/callback] ${MIGRATE_COOKIE} cookie deleted`)
      } else {
        console.log(`[auth/callback] no ${MIGRATE_COOKIE} cookie — skipping migrate_anon_interactions`)
      }

      return NextResponse.redirect(`${origin}/`)
    }
  }

  return NextResponse.redirect(`${origin}/account?error=auth_failed`)
}
