import request from 'superagent'
import { Message, Source } from '../types/Message'

const rootUrl = '/api/v1'

interface ChatResponse {
  reply: string
  sources: Source[]
}

export async function sendMessage(
  message: string,
  history: Message[],
): Promise<ChatResponse> {
  const response = await request
    .post(`${rootUrl}/chat`)
    .send({ message, history })
  return { reply: response.body.reply, sources: response.body.sources || [] }
}
