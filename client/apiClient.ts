import request from 'superagent'
import { Message } from '../types/Message'

const rootUrl = '/api/v1'

export async function sendMessage(
  message: string,
  history: Message[],
): Promise<string> {
  const response = await request
    .post(`${rootUrl}/chat`)
    .send({ message, history })
  return response.body.reply
}
