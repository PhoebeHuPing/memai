import request from 'superagent'
import { Message, Source } from '../types/Message'

const rootUrl = '/api/v1'

// Timeout configuration (ms)
const RESPONSE_TIMEOUT = 35000 // Time to wait for server to start responding
const DEADLINE_TIMEOUT = 60000 // Total time for the request to complete

export interface ChatResponse {
  id: string
  reply: string
  sources: Source[]
  no_context: boolean
  warning?: string
}

export interface ErrorResponse {
  error_code: string
  message: string
  detail?: string
}

export interface SessionInfo {
  session_id: string
  title: string
  last_active: number
}

/**
 * Parse a superagent error into a typed ErrorResponse.
 * Falls back to generic messages if the response body is not in our format.
 */
export function parseApiError(error: any): ErrorResponse {
  if (error?.response?.body?.error_code) {
    return error.response.body as ErrorResponse
  }

  // Superagent timeout errors
  if (error?.timeout || error?.code === 'ECONNABORTED') {
    return {
      error_code: 'timeout',
      message: 'The request timed out. The server may be busy — please try again.',
    }
  }

  // Network errors (no response at all)
  if (!error?.response) {
    return {
      error_code: 'network_error',
      message: 'Unable to reach the server. Please check your connection.',
    }
  }

  return {
    error_code: 'unknown',
    message: error?.message ?? 'An unexpected error occurred.',
  }
}

export async function getSessions(): Promise<SessionInfo[]> {
  const response = await request
    .get(`${rootUrl}/sessions`)
    .timeout({ response: RESPONSE_TIMEOUT, deadline: DEADLINE_TIMEOUT })
  return response.body
}

export async function getMessages(sessionId: string = 'default'): Promise<Message[]> {
  const response = await request
    .get(`${rootUrl}/messages`)
    .query({ session_id: sessionId })
    .timeout({ response: RESPONSE_TIMEOUT, deadline: DEADLINE_TIMEOUT })
  return response.body
}

export async function clearMessages(sessionId: string = 'default'): Promise<void> {
  await request
    .delete(`${rootUrl}/messages`)
    .query({ session_id: sessionId })
    .timeout({ response: RESPONSE_TIMEOUT, deadline: DEADLINE_TIMEOUT })
}

export async function sendMessage(
  messageId: string,
  message: string,
  history: Message[],
  sessionId: string = 'default',
): Promise<ChatResponse> {
  const response = await request
    .post(`${rootUrl}/chat`)
    .send({
      message_id: messageId,
      message,
      history,
      session_id: sessionId,
    })
    .timeout({ response: RESPONSE_TIMEOUT, deadline: DEADLINE_TIMEOUT })
  return {
    id: response.body.id,
    reply: response.body.reply,
    sources: response.body.sources || [],
    no_context: response.body.no_context ?? false,
    warning: response.body.warning,
  }
}

/**
 * Stream a chat response via SSE. Calls onToken for each text chunk,
 * onMeta when sources/no_context metadata arrives, and onDone when complete.
 */
export async function sendMessageStream(
  messageId: string,
  message: string,
  history: Message[],
  sessionId: string = 'default',
  callbacks: {
    onToken: (token: string) => void
    onMeta?: (meta: { sources: Source[]; no_context: boolean }) => void
    onDone: (data: { id: string; warning?: string }) => void
    onError: (error: string) => void
  },
): Promise<void> {
  const response = await fetch(`${rootUrl}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message_id: messageId,
      message,
      history,
      session_id: sessionId,
    }),
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null)
    callbacks.onError(
      errorBody?.message || errorBody?.detail || `HTTP ${response.status}`,
    )
    return
  }

  const reader = response.body?.getReader()
  if (!reader) {
    callbacks.onError('Streaming not supported by browser')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const jsonStr = line.slice(6)
      try {
        const data = JSON.parse(jsonStr)
        if (data.token !== undefined) {
          callbacks.onToken(data.token)
        } else if (data.sources !== undefined) {
          callbacks.onMeta?.({ sources: data.sources, no_context: data.no_context })
        } else if (data.done) {
          callbacks.onDone({ id: data.id, warning: data.warning })
        } else if (data.error) {
          callbacks.onError(data.error)
        }
      } catch {
        // Ignore malformed JSON lines
      }
    }
  }
}

export async function renameSession(sessionId: string, title: string): Promise<void> {
  await request
    .patch(`${rootUrl}/sessions/${sessionId}`)
    .send({ title })
    .timeout({ response: RESPONSE_TIMEOUT, deadline: DEADLINE_TIMEOUT })
}

export async function deleteSession(sessionId: string): Promise<void> {
  await request
    .delete(`${rootUrl}/sessions/${sessionId}`)
    .timeout({ response: RESPONSE_TIMEOUT, deadline: DEADLINE_TIMEOUT })
}
