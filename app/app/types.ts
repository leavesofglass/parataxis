export interface Poem {
  id: string
  title: string
  author: string
  body: string
  body_html?: string | null
  line_count: number
}
