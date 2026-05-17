import { getSupabase } from './supabase'

export type SendResult =
  | { ok: true; mode: 'confirm' | 'magic' }
  | { ok: false; error: string }

/**
 * Sends a sign-in / email-confirmation link to `email`.
 *
 * - Anonymous user: calls updateUser({ email }) to attach the email to their
 *   existing user_id, preserving their saved library.
 * - email_exists error: signs out the anonymous session first, then falls back
 *   to signInWithOtp so the PKCE challenge is initiated without an active user.
 *   (Without signOut the verifier is bound to the wrong user_id.)
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
      // Capture before signOut(): the migration handler needs this id to move
      // the anon user's interactions onto the existing account once the magic
      // link completes.
      const anonUserId = user.id
      await supabase.auth.signOut()

      const callbackUrl = new URL(redirectTo)
      callbackUrl.searchParams.set('migrate_from', anonUserId)

      const { error: otpErr } = await supabase.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: callbackUrl.toString() },
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
