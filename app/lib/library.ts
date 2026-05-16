import { getSupabase } from './supabase'
import type { Poem } from '../app/types'

export interface LibraryPoem extends Poem {
  isSuperLiked: boolean
}

/**
 * Returns saved poems for the current user, newest-first.
 * Groups interactions by poem_id, takes the most recent action per poem,
 * and includes the poem only if that action is 'save' or 'super_like'.
 */
export async function fetchLibrary(userId: string): Promise<LibraryPoem[]> {
  const supabase = getSupabase()

  // Fetch all relevant interactions for this user, ordered newest-first
  const { data: interactions, error: intError } = await supabase
    .from('interactions')
    .select('poem_id, action, created_at')
    .eq('user_id', userId)
    .in('action', ['save', 'super_like', 'unsave'])
    .order('created_at', { ascending: false })

  if (intError || !interactions) {
    console.error('fetchLibrary interactions error:', intError)
    return []
  }

  // Take most-recent interaction per poem_id
  const latestByPoem = new Map<string, { action: string; created_at: string }>()
  for (const row of interactions) {
    if (!latestByPoem.has(row.poem_id)) {
      latestByPoem.set(row.poem_id, { action: row.action, created_at: row.created_at })
    }
  }

  // Group: super-likes first (newest-first), then regular saves (newest-first).
  // latestByPoem's iteration order matches the input rows (already newest-first),
  // so each group preserves chronological order on its own.
  const superLikes: Array<{ poem_id: string; action: string }> = []
  const regularSaves: Array<{ poem_id: string; action: string }> = []
  for (const [poem_id, { action }] of latestByPoem) {
    if (action === 'super_like') superLikes.push({ poem_id, action })
    else if (action === 'save') regularSaves.push({ poem_id, action })
  }
  const saved = [...superLikes, ...regularSaves]

  if (saved.length === 0) return []

  const poemIds = saved.map((s) => s.poem_id)
  const { data: poems, error: poemError } = await supabase
    .from('poems')
    .select('id, title, author, body, line_count')
    .in('id', poemIds)

  if (poemError || !poems) {
    console.error('fetchLibrary poems error:', poemError)
    return []
  }

  // Merge and preserve newest-first order
  return saved
    .map(({ poem_id, action }) => {
      const poem = poems.find((p: Poem) => p.id === poem_id)
      if (!poem) return null
      return { ...poem, isSuperLiked: action === 'super_like' }
    })
    .filter(Boolean) as LibraryPoem[]
}

/** Count of currently-saved poems (save/super_like, not unsaved). */
export async function fetchSavedCount(userId: string): Promise<number> {
  const library = await fetchLibrary(userId)
  return library.length
}
