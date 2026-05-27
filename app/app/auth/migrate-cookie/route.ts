import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'

const MIGRATE_COOKIE = 'anon_user_id_for_migration'

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as { anon_user_id?: string } | null
  const anonUserId = body?.anon_user_id
  if (!anonUserId) {
    console.log('[auth/migrate-cookie] missing anon_user_id in request body')
    return NextResponse.json({ ok: false, error: 'anon_user_id required' }, { status: 400 })
  }

  const cookieStore = await cookies()
  cookieStore.set(MIGRATE_COOKIE, anonUserId, {
    httpOnly: true,
    sameSite: 'lax',
    secure: true,
    path: '/',
    maxAge: 3600,
  })
  console.log(`[auth/migrate-cookie] set ${MIGRATE_COOKIE}="${anonUserId}"`)
  return NextResponse.json({ ok: true })
}
