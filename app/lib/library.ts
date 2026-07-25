import { getSupabase } from './supabase'
import type { Poem } from '../app/types'

export interface LibraryPoem extends Poem {
  isSuperLiked: boolean
}

export interface SkippedPoem extends Poem {
  skippedAt: string
}

/**
 * Returns saved poems for the current user, newest-first.
 * Library = only rows with action='save' (not superseded by 'unsave').
 * Historical super_like rows are excluded — they remain in the DB as taste
 * signals for the recommender but do not appear in the library.
 */
export async function fetchLibrary(userId: string): Promise<LibraryPoem[]> {
  const supabase = getSupabase()

  // Fetch save and unsave interactions, newest-first
  const { data: interactions, error: intError } = await supabase
    .from('interactions')
    .select('poem_id, action, created_at')
    .eq('user_id', userId)
    .in('action', ['save', 'unsave'])
    .order('created_at', { ascending: false })

  if (intError || !interactions) {
    console.error('fetchLibrary interactions error:', intError)
    return []
  }

  // Take most-recent interaction per poem_id; include only if it's 'save'
  const latestByPoem = new Map<string, string>()
  for (const row of interactions) {
    if (!latestByPoem.has(row.poem_id)) {
      latestByPoem.set(row.poem_id, row.action)
    }
  }

  const savedIds: string[] = []
  for (const [poem_id, action] of latestByPoem) {
    if (action === 'save') savedIds.push(poem_id)
  }

  if (savedIds.length === 0) return []

  const { data: poems, error: poemError } = await supabase
    .rpc('get_poems_by_ids', { poem_ids: savedIds })

  if (poemError || !poems) {
    console.error('fetchLibrary poems error:', poemError)
    return []
  }

  // Preserve newest-first order from savedIds
  const byId = new Map((poems as Poem[]).map((p) => [p.id, p]))
  return savedIds
    .map((id) => {
      const poem = byId.get(id)
      if (!poem) return null
      return { ...poem, isSuperLiked: false }
    })
    .filter(Boolean) as LibraryPoem[]
}

/** Count of currently-saved poems (action='save', not superseded by 'unsave'). */
export async function fetchSavedCount(userId: string): Promise<number> {
  const library = await fetchLibrary(userId)
  return library.length
}

/**
 * Returns poems the user has skipped (interactions where action = 'dislike'),
 * newest-first. Deduplicated by poem_id — if the user un-skipped then re-skipped
 * the same poem, only the most recent dislike row is reflected.
 */
export async function fetchSkipped(userId: string): Promise<SkippedPoem[]> {
  const supabase = getSupabase()

  const { data: interactions, error: intError } = await supabase
    .from('interactions')
    .select('poem_id, created_at')
    .eq('user_id', userId)
    .eq('action', 'dislike')
    .order('created_at', { ascending: false })

  if (intError || !interactions) {
    console.error('fetchSkipped interactions error:', intError)
    return []
  }

  if (interactions.length === 0) return []

  const poemIds = Array.from(
    new Set((interactions as { poem_id: string; created_at: string }[]).map((i) => i.poem_id)),
  )
  const { data: poems, error: poemError } = await supabase
    .rpc('get_poems_by_ids', { poem_ids: poemIds })

  if (poemError || !poems) {
    console.error('fetchSkipped poems error:', poemError)
    return []
  }

  const byId = new Map((poems as Poem[]).map((p) => [p.id, p]))
  const seen = new Set<string>()
  const result: SkippedPoem[] = []
  for (const row of interactions) {
    if (seen.has(row.poem_id)) continue
    seen.add(row.poem_id)
    const poem = byId.get(row.poem_id)
    if (poem) result.push({ ...poem, skippedAt: row.created_at })
  }
  return result
}
