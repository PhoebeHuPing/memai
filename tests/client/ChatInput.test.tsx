import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatInput from '../../client/components/ChatInput'

describe('ChatInput Component', () => {
  const onSendMessage = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    cleanup()
  })

  const renderInput = (disabled = false) => {
    return render(
      <ChatInput onSendMessage={onSendMessage} disabled={disabled} />,
    )
  }

  it('should render textarea and send button', () => {
    renderInput()

    expect(
      screen.getByPlaceholderText(/Type your message/),
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: /Send/ })).toBeTruthy()
  })

  it('should send message on form submit', async () => {
    renderInput()

    const textarea = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(textarea, 'Hello world')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    expect(onSendMessage).toHaveBeenCalledWith('Hello world')
  })

  it('should clear input after sending', async () => {
    renderInput()

    const textarea = screen.getByPlaceholderText(
      /Type your message/,
    ) as HTMLTextAreaElement
    await userEvent.type(textarea, 'Will be cleared')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    expect(textarea.value).toBe('')
  })

  it('should not send empty or whitespace-only messages', async () => {
    renderInput()

    const textarea = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(textarea, '   ')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    expect(onSendMessage).not.toHaveBeenCalled()
  })

  it('should trim message before sending', async () => {
    renderInput()

    const textarea = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(textarea, '  trimmed message  ')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    expect(onSendMessage).toHaveBeenCalledWith('trimmed message')
  })

  describe('Keyboard shortcuts', () => {
    it('should send on Enter (without modifiers)', async () => {
      renderInput()

      const textarea = screen.getByPlaceholderText(/Type your message/)
      await userEvent.type(textarea, 'Enter test')
      fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' })

      expect(onSendMessage).toHaveBeenCalledWith('Enter test')
    })

    it('should NOT send on Shift+Enter', async () => {
      renderInput()

      const textarea = screen.getByPlaceholderText(/Type your message/)
      await userEvent.type(textarea, 'Newline test')
      fireEvent.keyDown(textarea, {
        key: 'Enter',
        code: 'Enter',
        shiftKey: true,
      })

      expect(onSendMessage).not.toHaveBeenCalled()
    })

    it('should send on Ctrl+Enter', async () => {
      renderInput()

      const textarea = screen.getByPlaceholderText(/Type your message/)
      await userEvent.type(textarea, 'Ctrl enter')
      fireEvent.keyDown(textarea, {
        key: 'Enter',
        code: 'Enter',
        ctrlKey: true,
      })

      expect(onSendMessage).toHaveBeenCalledWith('Ctrl enter')
    })

    it('should send on Meta+Enter (macOS Cmd)', async () => {
      renderInput()

      const textarea = screen.getByPlaceholderText(/Type your message/)
      await userEvent.type(textarea, 'Cmd enter')
      fireEvent.keyDown(textarea, {
        key: 'Enter',
        code: 'Enter',
        metaKey: true,
      })

      expect(onSendMessage).toHaveBeenCalledWith('Cmd enter')
    })
  })

  describe('Disabled state', () => {
    it('should disable textarea when disabled prop is true', () => {
      renderInput(true)

      const textarea = screen.getByPlaceholderText(
        /Type your message/,
      ) as HTMLTextAreaElement
      expect(textarea.disabled).toBe(true)
    })

    it('should disable send button when disabled prop is true', () => {
      renderInput(true)

      const button = screen.getByRole('button', {
        name: /Send/,
      }) as HTMLButtonElement
      expect(button.disabled).toBe(true)
    })

    it('should disable send button when input is empty', () => {
      renderInput()

      const button = screen.getByRole('button', {
        name: /Send/,
      }) as HTMLButtonElement
      expect(button.disabled).toBe(true)
    })

    it('should not send when disabled even if input has text', async () => {
      const { rerender } = render(
        <ChatInput onSendMessage={onSendMessage} disabled={false} />,
      )

      const textarea = screen.getByPlaceholderText(/Type your message/)
      await userEvent.type(textarea, 'Should not send')

      rerender(<ChatInput onSendMessage={onSendMessage} disabled={true} />)

      fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' })

      expect(onSendMessage).not.toHaveBeenCalled()
    })
  })

  describe('Auto-resize', () => {
    it('should set textarea height based on scrollHeight', async () => {
      renderInput()

      const textarea = screen.getByPlaceholderText(
        /Type your message/,
      ) as HTMLTextAreaElement

      // jsdom doesn't compute layout, so scrollHeight is 0.
      // We verify that the effect sets the style (height = '0px' since
      // scrollHeight is 0 in jsdom). The important thing is that the
      // style.height is being set dynamically.
      await userEvent.type(textarea, 'Some text')

      // In jsdom scrollHeight is 0, so min(0, 180) = 0
      expect(textarea.style.height).toBe('0px')
    })

    it('should cap height at 180px', async () => {
      renderInput()

      const textarea = screen.getByPlaceholderText(
        /Type your message/,
      ) as HTMLTextAreaElement

      // Simulate a large scrollHeight
      Object.defineProperty(textarea, 'scrollHeight', {
        value: 300,
        configurable: true,
      })

      await userEvent.type(textarea, 'A')

      expect(textarea.style.height).toBe('180px')
    })
  })
})
