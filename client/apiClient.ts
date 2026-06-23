import request from 'superagent'
import { Message, Source } from '../types/Message'

const rootUrl = '/api/v1'

interface ChatResponse {
  id: string
  reply: string
  sources: Source[]
}

export async function getMessages(sessionId: string = 'default'): Promise<Message[]> {
  const response = await request.get(`${rootUrl}/messages`).query({ session_id: sessionId })
  return response.body
}

export async function clearMessages(sessionId: string = 'default'): Promise<void> {
  await request.delete(`${rootUrl}/messages`).query({ session_id: sessionId })
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
      session_id: sessionId 
    })
  return { id: response.body.id, reply: response.body.reply, sources: response.body.sources || [] }
}
