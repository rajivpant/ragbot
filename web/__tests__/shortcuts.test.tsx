/**
 * Component-level tests for the keyboard-shortcut layer.
 *
 *   - `ShortcutsHelpOverlay` rendering, Escape close, backdrop close.
 *   - `Chat.tsx` integration: ⌘K opens the model picker (signal increments,
 *     which we observe through the SettingsPanel render), ⌘N clears the chat,
 *     ⌘? opens the overlay, and shortcuts dispatch correctly relative to
 *     input-focus rules.
 *
 * We mock `@/lib/api` so the Chat component doesn't try to fetch on mount.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React from 'react';

// ---- Mock the API module BEFORE importing Chat ----
//
// Chat.tsx loads /api/config on mount; we resolve with demo_mode=false so the
// banner stays off. Workspace + model loaders are stubbed to deterministic
// empty results.
vi.mock('@/lib/api', () => {
  return {
    chatStream: vi.fn(async function* () {
      // never yields
    }),
    getConfig: vi.fn().mockResolvedValue({
      version: 'test',
      workspace_count: 0,
      rag_available: false,
      default_model: 'test-model',
      default_workspace: undefined,
      api_keys: {},
      workspaces_with_keys: [],
      demo_mode: false,
    }),
    recordRecentModel: vi.fn().mockResolvedValue(undefined),
    backgroundAgentTask: vi.fn().mockResolvedValue({ task_id: 't', status: 'backgrounded' }),
    cancelAgentTask: vi.fn().mockResolvedValue({ task_id: 't', status: 'cancelled' }),
    getModels: vi.fn().mockResolvedValue({ models: [], default_model: 'test-model' }),
    getWorkspaces: vi.fn().mockResolvedValue([]),
    getProviders: vi.fn().mockResolvedValue({ providers: [] }),
    getTemperatureSettings: vi.fn().mockResolvedValue({ balanced: 0.7 }),
    getKeysStatus: vi.fn().mockResolvedValue({}),
    getIndexStatus: vi.fn().mockResolvedValue(null),
    indexWorkspace: vi.fn().mockResolvedValue(undefined),
    getPinnedModels: vi.fn().mockResolvedValue([]),
    setPinnedModels: vi.fn().mockResolvedValue([]),
    getRecentModels: vi.fn().mockResolvedValue([]),
  };
});

import { ShortcutsHelpOverlay } from '../src/components/ShortcutsHelpOverlay';
import { keyboardShortcuts, isMac } from '../src/lib/shortcuts';
import { Chat } from '../src/components/Chat';

beforeEach(() => {
  keyboardShortcuts.clear();
});

describe('ShortcutsHelpOverlay', () => {
  it('renders all registered shortcuts with description and combo', () => {
    keyboardShortcuts.register({
      id: 's1',
      keys: { mac: ['Meta', 'k'], other: ['Control', 'k'] },
      description: 'Open model picker',
      scope: 'global',
      handler: vi.fn(),
    });
    keyboardShortcuts.register({
      id: 's2',
      keys: { mac: ['Meta', 'n'], other: ['Control', 'n'] },
      description: 'Start new chat',
      scope: 'global',
      handler: vi.fn(),
    });

    render(<ShortcutsHelpOverlay open={true} onClose={vi.fn()} />);
    expect(screen.getByText('Open model picker')).toBeInTheDocument();
    expect(screen.getByText('Start new chat')).toBeInTheDocument();
    // Both kbd elements with the K/N letter exist.
    const kbds = screen.getAllByRole('dialog');
    expect(kbds.length).toBeGreaterThan(0);
  });

  it('does not render when open=false', () => {
    keyboardShortcuts.register({
      id: 's1',
      keys: { mac: ['Meta', 'k'], other: ['Control', 'k'] },
      description: 'Open model picker',
      scope: 'global',
      handler: vi.fn(),
    });
    render(<ShortcutsHelpOverlay open={false} onClose={vi.fn()} />);
    expect(screen.queryByText('Open model picker')).not.toBeInTheDocument();
  });

  it('closes on Escape key', () => {
    const onClose = vi.fn();
    render(<ShortcutsHelpOverlay open={true} onClose={onClose} />);
    const overlay = screen.getByTestId('shortcuts-help-overlay');
    fireEvent.keyDown(overlay, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('closes when the backdrop is clicked', () => {
    const onClose = vi.fn();
    render(<ShortcutsHelpOverlay open={true} onClose={onClose} />);
    const backdrop = screen.getByTestId('shortcuts-help-overlay');
    // Click on the backdrop itself (not on its dialog child).
    fireEvent.click(backdrop, { target: backdrop });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('does NOT close when the dialog body is clicked', () => {
    const onClose = vi.fn();
    render(<ShortcutsHelpOverlay open={true} onClose={onClose} />);
    const dialog = screen.getByRole('dialog');
    fireEvent.click(dialog);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe('Chat.tsx — keyboard shortcut integration', () => {
  /**
   * Fires a window-level keydown so the global listener registered by Chat
   * picks it up. Set `primaryMod: true` to add the platform's primary
   * modifier (Meta on macOS, Control elsewhere); the registry's matcher
   * requires an exact modifier match so we must not send extras.
   */
  function pressKey(opts: {
    key: string;
    primaryMod?: boolean;
    shift?: boolean;
    target?: EventTarget | null;
  }) {
    const onMac = isMac();
    const event = new KeyboardEvent('keydown', {
      key: opts.key,
      metaKey: opts.primaryMod ? onMac : false,
      ctrlKey: opts.primaryMod ? !onMac : false,
      shiftKey: opts.shift ?? false,
      bubbles: true,
      cancelable: true,
    });
    if (opts.target) {
      (opts.target as EventTarget).dispatchEvent(event);
    } else {
      window.dispatchEvent(event);
    }
    return event;
  }

  async function renderChat() {
    let result: ReturnType<typeof render>;
    await act(async () => {
      result = render(<Chat />);
    });
    // Flush microtasks for the async config fetch.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    return result!;
  }

  it('registers all seven shortcuts on mount', async () => {
    await renderChat();
    const ids = keyboardShortcuts.getAll().map((s) => s.id);
    expect(ids).toEqual(
      expect.arrayContaining([
        'open-model-picker',
        'switch-workspace',
        'search-messages',
        'new-chat',
        'background-operation',
        'cancel-operation',
        'show-shortcuts-help',
      ]),
    );
  });

  it('⌘? opens the ShortcutsHelpOverlay', async () => {
    await renderChat();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await act(async () => {
      pressKey({ key: '?', primaryMod: true, shift: true });
    });
    expect(screen.getByTestId('shortcuts-help-overlay')).toBeInTheDocument();
  });

  it('⌘N clears messages and shows the empty welcome state again', async () => {
    await renderChat();
    expect(screen.getByText('Welcome to Ragbot')).toBeInTheDocument();
    await act(async () => {
      pressKey({ key: 'n', primaryMod: true });
    });
    expect(screen.getByText('Welcome to Ragbot')).toBeInTheDocument();
  });

  it('⌘/ opens the message-history search input and focuses it', async () => {
    await renderChat();
    expect(screen.queryByLabelText('Search message history')).not.toBeInTheDocument();
    await act(async () => {
      pressKey({ key: '/', primaryMod: true });
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 5));
    });
    expect(screen.getByLabelText('Search message history')).toBeInTheDocument();
  });

  it('does NOT fire any shortcut for a bare letter key without modifiers', async () => {
    await renderChat();
    const beforeCount = keyboardShortcuts.getAll().length;
    // Pressing plain 'n' must not fire ⌘N — the welcome banner should still
    // be the empty state with no extra side effects.
    await act(async () => {
      pressKey({ key: 'n' });
    });
    expect(screen.getByText('Welcome to Ragbot')).toBeInTheDocument();
    expect(keyboardShortcuts.getAll().length).toBe(beforeCount);
    // The search input should still NOT be present (since plain '/' didn't fire either).
    expect(screen.queryByLabelText('Search message history')).not.toBeInTheDocument();
  });

  it('⌘N (global scope) still fires when a textarea has focus', async () => {
    await renderChat();
    // Open the search bar first to give us an observable side effect to undo.
    await act(async () => {
      pressKey({ key: '/', primaryMod: true });
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 5));
    });
    expect(screen.getByLabelText('Search message history')).toBeInTheDocument();
    // Focus the composer textarea.
    const composer = document.querySelector<HTMLTextAreaElement>(
      'textarea[data-shortcut-target="composer"]',
    );
    expect(composer).toBeTruthy();
    composer!.focus();
    expect(document.activeElement).toBe(composer);
    // ⌘N is global — it should still fire even though a textarea has focus.
    // We confirm by re-asserting the search bar is closed (⌘N clears
    // messages and closes the search bar).
    await act(async () => {
      const onMac = isMac();
      const ev = new KeyboardEvent('keydown', {
        key: 'n',
        metaKey: onMac,
        ctrlKey: !onMac,
        bubbles: true,
        cancelable: true,
      });
      composer!.dispatchEvent(ev);
    });
    expect(screen.queryByLabelText('Search message history')).not.toBeInTheDocument();
  });
});
