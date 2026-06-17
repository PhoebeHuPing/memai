export interface Source {
  file: string
  page: string
  score: number | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  sources?: Source[]
}
