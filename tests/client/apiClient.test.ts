import { describe, it, expect, vi, beforeEach } from 'vitest'
import { sendMessage } from '../../client/apiClient'
import request from 'superagent'
import { Message } from '../../types/Message'

vi.mock('superagent')

describe('sendMessage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should send a message and return the AI reply', async () => {
    const mockReply = 'Hello! How can I help you?'
    vi.mocked(request.post).mockReturnValue({
      send: vi.fn().mockResolvedValue({
        body: { reply: mockReply },
      }),
    } as any)

    const result = await sendMessage('hi', [])

    expect(result).toBe(mockReply)
    expect(request.post).toHaveBeenCalledWith('/api/v1/chat')
  })

  it('should send conversation history with the message', async () => {
    const mockReply = 'That sounds great!'
    const sendMock = vi.fn().mockResolvedValue({
      body: { reply: mockReply },
    })
    vi.mocked(request.post).mockReturnValue({
      send: sendMock,
    } as any)

    const history: Message[] = [
      { id: '1', role: 'user', content: 'hello', timestamp: Date.now() },
      { id: '2', role: 'assistant', content: 'hi there', timestamp: Date.now() },
    ]
    const message = 'how are you?'

    const result = await sendMessage(message, history)

    expect(result).toBe(mockReply)
    expect(request.post).toHaveBeenCalledWith('/api/v1/chat')
    expect(sendMock).toHaveBeenCalledWith({ message, history })
  })

  it('should handle errors appropriately', async () => {
    vi.mocked(request.post).mockReturnValue({
      send: vi.fn().mockRejectedValue(new Error('Network error')),
    } as any)

    await expect(sendMessage('hi', [])).rejects.toThrow('Network error')
  })
})
