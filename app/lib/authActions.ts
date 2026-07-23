import { getSupabase } from './supabase'

export type SendResult =
  | { ok: true; mode: 'confirm' | 'magic' }
  | { ok: false; error: string }

const MIGRATE_COOKIE_ENDPOINT = '/auth/migrate-cookie'

async function setMigrateCookieIfAnon(): Promise<void> {
  const supabase = getSupabase()
  const { data: { user } } = await supabase.auth.getUser()
  if (user?.is_anonymous !== true) return
  try {
    await fetch(MIGRATE_COOKIE_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anon_user_id: user.id }),
    })
  } catch (e) {
    console.error('[authActions] failed to set migrate cookie:', e)
  }
}

export async function signInWithGoogle(redirectTo: string): Promise<{ error: string | null }> {
  await setMigrateCookieIfAnon()
  const supabase = getSupabase()
  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo },
  })
  return { error: error?.message ?? null }
}

/**
 * Sends a sign-in / email-confirmation link to `email`.
 *
 * - Anonymous user: calls updateUser({ email }) to attach the email to their
 *   existing user_id, preserving their saved library.
 * - email_exists error: stashes the anon user_id in an httpOnly cookie via a
 *   server endpoint, then falls back to signInWithOtp. The auth callback
 *   reads the cookie and runs migrate_anon_interactions before clearing it.
 *   The anon session is intentionally left in place — supabase replaces it
 *   on callback, so the library stays visible while the user waits for the
 *   email. (Earlier versions used a migrate_from URL param, but magic-link
 *   providers can strip custom params, so the cookie is the source of truth.)
 * - No session or non-anonymous user: calls signInWithOtp directly.
 */
export async function sendSignInLink(
  email: string,
  redirectTo: string,
): Promise<SendResult> {
  const supabase = getSupabase()
  const { data: { user } } = await supabase.auth.getUser()

  if (user?.is_anonymous === true) {
    const { error } = await supabase.auth.updateUser(
      { email },
      { emailRedirectTo: redirectTo },
    )

    if (!error) return { ok: true, mode: 'confirm' }

    if (error.code === 'email_exists') {
      const anonUserId = user.id

      try {
        const res = await fetch(MIGRATE_COOKIE_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ anon_user_id: anonUserId }),
        })
        if (res.ok) {
          console.log('[authActions] migrate cookie set for anon_user_id:', anonUserId)
        } else {
          console.error('[authActions] migrate cookie endpoint returned', res.status)
        }
      } catch (e) {
        console.error('[authActions] failed to set migrate cookie:', e)
      }

      const { error: otpErr } = await supabase.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: redirectTo },
      })
      if (otpErr) return { ok: false, error: otpErr.message }
      return { ok: true, mode: 'magic' }
    }

    return { ok: false, error: error.message }
  }

  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: redirectTo },
  })
  if (error) return { ok: false, error: error.message }
  return { ok: true, mode: 'magic' }
}
