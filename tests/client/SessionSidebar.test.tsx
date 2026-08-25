import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SessionSidebar from '../../client/components/SessionSidebar'
import * as apiClient from '../../client/apiClient'

vi.mock('../../client/apiClient', () => ({
  getSessions: vi.fn(),
  renameSession: vi.fn(),
  deleteSession: vi.fn(),
}))

const mockGetSessions = vi.mocked(apiClient.getSessions)
const mockRenameSession = vi.mocked(apiClient.renameSession)
const mockDeleteSession = vi.mocked(apiClient.deleteSession)

const mockSessions: apiClient.SessionInfo[] = [
  { session_id: 'session-1', title: '5YA Questions', last_active: Date.now() },
  {
    session_id: 'session-2',
    title: 'Property Policy',
    last_active: Date.now() - 86400000,
  },
]

describe('SessionSidebar Component', () => {
  let queryClient: QueryClient
  const onSelectSession = vi.fn()
  const onNewSession = vi.fn()
  const onSessionDeleted = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    mockGetSessions.mockResolvedValue(mockSessions)
  })

  afterEach(() => {
    cleanup()
  })

  const renderSidebar = (currentSessionId = 'session-1') => {
    return render(
      <QueryClientProvider client={queryClient}>
        <SessionSidebar
          currentSessionId={currentSessionId}
          onSelectSession={onSelectSession}
          onNewSession={onNewSession}
          onSessionDeleted={onSessionDeleted}
        />
      </QueryClientProvider>,
    )
  }

  it('should render session list from API', async () => {
    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('5YA Questions')).toBeTruthy()
      expect(screen.getByText('Property Policy')).toBeTruthy()
    })
  })

  it('should show empty state when no sessions exist', async () => {
    mockGetSessions.mockResolvedValue([])
    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('No conversations yet')).toBeTruthy()
    })
  })

  it('should highlight the active session', async () => {
    renderSidebar('session-1')

    await waitFor(() => {
      expect(screen.getByText('5YA Questions')).toBeTruthy()
    })

    const activeItem = screen.getByText('5YA Questions').closest('.session-item')
    expect(activeItem?.classList.contains('active')).toBe(true)

    const inactiveItem = screen
      .getByText('Property Policy')
      .closest('.session-item')
    expect(inactiveItem?.classList.contains('active')).toBe(false)
  })

  it('should call onSelectSession when clicking a session', async () => {
    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('Property Policy')).toBeTruthy()
    })

    const sessionButton = screen.getByText('Property Policy').closest('button')
    fireEvent.click(sessionButton!)

    expect(onSelectSession).toHaveBeenCalledWith('session-2')
  })

  it('should call onNewSession when clicking "+ New" button', async () => {
    renderSidebar()

    const newButton = screen.getByRole('button', { name: /New chat/ })
    fireEvent.click(newButton)

    expect(onNewSession).toHaveBeenCalled()
  })

  describe('Rename', () => {
    it('should enter edit mode when clicking rename button', async () => {
      renderSidebar()

      await waitFor(() => {
        expect(screen.getByText('5YA Questions')).toBeTruthy()
      })

      const renameButtons = screen.getAllByRole('button', {
        name: /Rename conversation/,
      })
      fireEvent.click(renameButtons[0])

      const input = screen.getByDisplayValue('5YA Questions')
      expect(input).toBeTruthy()
      expect(input.tagName).toBe('INPUT')
    })

    it('should confirm rename on Enter', async () => {
      mockRenameSession.mockResolvedValue(undefined)
      renderSidebar()

      await waitFor(() => {
        expect(screen.getByText('5YA Questions')).toBeTruthy()
      })

      const renameButtons = screen.getAllByRole('button', {
        name: /Rename conversation/,
      })
      fireEvent.click(renameButtons[0])

      const input = screen.getByDisplayValue('5YA Questions')
      await userEvent.clear(input)
      await userEvent.type(input, 'Renamed Session')
      fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' })

      await waitFor(() => {
        expect(mockRenameSession).toHaveBeenCalledWith(
          'session-1',
          'Renamed Session',
        )
      })
    })

    it('should cancel rename on Escape', async () => {
      renderSidebar()

      await waitFor(() => {
        expect(screen.getByText('5YA Questions')).toBeTruthy()
      })

      const renameButtons = screen.getAllByRole('button', {
        name: /Rename conversation/,
      })
      fireEvent.click(renameButtons[0])

      const input = screen.getByDisplayValue('5YA Questions')
      await userEvent.clear(input)
      await userEvent.type(input, 'Should not save')
      fireEvent.keyDown(input, { key: 'Escape', code: 'Escape' })

      // Should exit edit mode without calling rename
      expect(mockRenameSession).not.toHaveBeenCalled()
      await waitFor(() => {
        expect(screen.queryByDisplayValue('Should not save')).toBeNull()
      })
    })

    it('should confirm rename on blur', async () => {
      mockRenameSession.mockResolvedValue(undefined)
      renderSidebar()

      await waitFor(() => {
        expect(screen.getByText('5YA Questions')).toBeTruthy()
      })

      const renameButtons = screen.getAllByRole('button', {
        name: /Rename conversation/,
      })
      fireEvent.click(renameButtons[0])

      const input = screen.getByDisplayValue('5YA Questions')
      await userEvent.clear(input)
      await userEvent.type(input, 'Blur Rename')
      fireEvent.blur(input)

      await waitFor(() => {
        expect(mockRenameSession).toHaveBeenCalledWith(
          'session-1',
          'Blur Rename',
        )
      })
    })

    it('should not call rename if input is empty', async () => {
      renderSidebar()

      await waitFor(() => {
        expect(screen.getByText('5YA Questions')).toBeTruthy()
      })

      const renameButtons = screen.getAllByRole('button', {
        name: /Rename conversation/,
      })
      fireEvent.click(renameButtons[0])

      const input = screen.getByDisplayValue('5YA Questions')
      await userEvent.clear(input)
      fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' })

      expect(mockRenameSession).not.toHaveBeenCalled()
    })
  })

  describe('Delete', () => {
    it('should show confirm dialog and delete on confirm', async () => {
      mockDeleteSession.mockResolvedValue(undefined)
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

      renderSidebar()

      await waitFor(() => {
        expect(screen.getByText('5YA Questions')).toBeTruthy()
      })

      const deleteButtons = screen.getAllByRole('button', {
        name: /Delete conversation/,
      })
      fireEvent.click(deleteButtons[0])

      expect(confirmSpy).toHaveBeenCalledWith(
        'Delete this conversation? This cannot be undone.',
      )

      await waitFor(() => {
        expect(mockDeleteSession).toHaveBeenCalledWith('session-1')
      })

      await waitFor(() => {
        expect(onSessionDeleted).toHaveBeenCalledWith('session-1')
      })

      confirmSpy.mockRestore()
    })

    it('should not delete when confirm is cancelled', async () => {
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

      renderSidebar()

      await waitFor(() => {
        expect(screen.getByText('5YA Questions')).toBeTruthy()
      })

      const deleteButtons = screen.getAllByRole('button', {
        name: /Delete conversation/,
      })
      fireEvent.click(deleteButtons[0])

      expect(confirmSpy).toHaveBeenCalled()
      expect(mockDeleteSession).not.toHaveBeenCalled()

      confirmSpy.mockRestore()
    })
  })

  describe('Time formatting', () => {
    it('should show "Yesterday" for sessions from one day ago', async () => {
      const yesterday = Date.now() - 86400000
      mockGetSessions.mockResolvedValue([
        { session_id: 's1', title: 'Yesterday Chat', last_active: yesterday },
      ])

      renderSidebar()

      await waitFor(() => {
        expect(screen.getByText('Yesterday')).toBeTruthy()
      })
    })

    it('should show "X days ago" for sessions within a week', async () => {
      const threeDaysAgo = Date.now() - 3 * 86400000
      mockGetSessions.mockResolvedValue([
        { session_id: 's1', title: 'Old Chat', last_active: threeDaysAgo },
      ])

      renderSidebar()

      await waitFor(() => {
        expect(screen.getByText('3 days ago')).toBeTruthy()
      })
    })
  })
})
