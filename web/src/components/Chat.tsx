'use client';

import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import {
  Message,
  chatStream,
  getConfig,
  recordRecentModel,
  backgroundAgentTask,
  cancelAgentTask,
  type ThinkingEffort,
} from '@/lib/api';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { SettingsPanel } from './SettingsPanel';
import { ShortcutsHelpOverlay } from './ShortcutsHelpOverlay';
import { keyboardShortcuts } from '@/lib/shortcuts';

// Simple token counter (approx 4 chars per token)
function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  // Settings state
  const [workspace, setWorkspace] = useState<string | undefined>();
  const [model, setModel] = useState<string | undefined>();
  const [temperature, setTemperature] = useState(0.75);
  const [useRag, setUseRag] = useState(true);
  const [ragMaxTokens, setRagMaxTokens] = useState(16000);
  const [maxTokens, setMaxTokens] = useState(4096);
  const [showSettings, setShowSettings] = useState(true); // Start expanded
  // v3 reasoning + cross-workspace controls
  const [thinkingEffort, setThinkingEffort] = useState<ThinkingEffort | undefined>(undefined);
  const [includeSkills, setIncludeSkills] = useState<boolean>(true);
  // v3.2: server-reported demo mode. Surfaced as a banner so screenshots
  // taken with RAGBOT_DEMO=1 are unmistakably demo.
  const [demoMode, setDemoMode] = useState<boolean>(false);
  // Counter incremented when ⌘K (Ctrl+K) is pressed outside a text input;
  // SettingsPanel watches this to open the ModelPicker imperatively.
  const [openModelPickerSignal, setOpenModelPickerSignal] = useState<number>(0);

  // ⌘? help overlay open state.
  const [showShortcutsHelp, setShowShortcutsHelp] = useState<boolean>(false);

  // ⌘/ message-history search filter. The search input lives in the messages
  // pane; when present, only messages whose content matches (case-insensitive
  // substring) are shown.
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showSearch, setShowSearch] = useState<boolean>(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // Toast surface for ⌘B / ⌘. when there's no active agent run, and for
  // generic transient feedback ("background requested", "cancelled", etc.).
  const [toast, setToast] = useState<{ message: string; tone: 'info' | 'error' } | null>(null);
  const toastTimerRef = useRef<number | null>(null);
  const showToast = useCallback((message: string, tone: 'info' | 'error' = 'info') => {
    setToast({ message, tone });
    if (toastTimerRef.current !== null) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(null), 3000);
  }, []);

  // Tracks the agent task id of the in-flight operation, if any. The chat
  // stream currently doesn't expose a task id, but skill runs and future
  // agent dispatches do; this hook is wired into both control shortcuts so
  // ⌘B and ⌘. work the moment any subsystem populates the id.
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const currentTaskIdRef = useRef<string | null>(null);
  useEffect(() => {
    currentTaskIdRef.current = currentTaskId;
  }, [currentTaskId]);

  // Workspace switcher trigger. Incrementing this scrolls the SettingsPanel
  // into view and moves focus to the workspace <select>.
  const [openWorkspaceSwitcherSignal, setOpenWorkspaceSwitcherSignal] = useState<number>(0);
  useEffect(() => {
    if (openWorkspaceSwitcherSignal === 0) return;
    // Use a tiny delay so the SettingsPanel is rendered (it auto-opens
    // below). Target by an accessible label since the panel isn't a child
    // ref; this stays decoupled from the panel's internal structure.
    const id = window.setTimeout(() => {
      const wsSelect = document.querySelector<HTMLSelectElement>(
        'select[aria-label="Workspace"], select[data-shortcut-target="workspace"]',
      );
      if (wsSelect) {
        wsSelect.focus();
        wsSelect.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        // Fallback: open Settings if collapsed and refocus on next tick.
        setShowSettings(true);
      }
    }, 50);
    return () => window.clearTimeout(id);
  }, [openWorkspaceSwitcherSignal]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Poll /api/config once on mount for demo_mode (and any future
  // server-driven UI flags).
  useEffect(() => {
    getConfig()
      .then((cfg) => setDemoMode(Boolean(cfg.demo_mode)))
      .catch(() => {
        /* ignore — banner just stays off if the call fails */
      });
  }, []);

  // Action handlers for shortcuts. Stable identities via useCallback so the
  // registration effect doesn't churn on every render.
  const openModelPicker = useCallback((e: KeyboardEvent) => {
    e.preventDefault();
    setOpenModelPickerSignal((n) => n + 1);
    setShowSettings(true);
  }, []);

  const openWorkspaceSwitcher = useCallback((e: KeyboardEvent) => {
    e.preventDefault();
    setShowSettings(true);
    setOpenWorkspaceSwitcherSignal((n) => n + 1);
  }, []);

  const focusMessageSearch = useCallback((e: KeyboardEvent) => {
    e.preventDefault();
    setShowSearch(true);
    // Wait one tick so the input is in the DOM before focusing.
    window.setTimeout(() => {
      searchInputRef.current?.focus();
      searchInputRef.current?.select();
    }, 0);
  }, []);

  const startNewChat = useCallback((e: KeyboardEvent) => {
    e.preventDefault();
    setMessages([]);
    setSearchQuery('');
    setShowSearch(false);
    // Focus the composer textarea so the user can type immediately.
    window.setTimeout(() => {
      const composer = document.querySelector<HTMLTextAreaElement>(
        'textarea[data-shortcut-target="composer"], textarea',
      );
      composer?.focus();
    }, 0);
  }, []);

  const backgroundCurrent = useCallback(
    (e: KeyboardEvent) => {
      e.preventDefault();
      const taskId = currentTaskIdRef.current;
      if (!taskId) {
        showToast('No active agent run to background.', 'info');
        return;
      }
      backgroundAgentTask(taskId)
        .then(() => showToast(`Backgrounded task ${taskId.slice(0, 8)}.`, 'info'))
        .catch((err: Error) =>
          showToast(`Background failed: ${err.message}`, 'error'),
        );
    },
    [showToast],
  );

  const cancelCurrent = useCallback(
    (e: KeyboardEvent) => {
      e.preventDefault();
      const taskId = currentTaskIdRef.current;
      if (!taskId) {
        showToast('No active agent run to cancel.', 'info');
        return;
      }
      cancelAgentTask(taskId)
        .then(() => {
          showToast(`Cancelled task ${taskId.slice(0, 8)}.`, 'info');
          setCurrentTaskId(null);
        })
        .catch((err: Error) =>
          showToast(`Cancel failed: ${err.message}`, 'error'),
        );
    },
    [showToast],
  );

  const toggleHelp = useCallback((e: KeyboardEvent) => {
    e.preventDefault();
    setShowShortcutsHelp((v) => !v);
  }, []);

  // Register every shortcut + bind one window-level keydown listener that
  // delegates to the registry. Registry membership is stable across renders;
  // we re-register handlers when their closures change so the registry
  // always invokes the latest version.
  useEffect(() => {
    keyboardShortcuts.register({
      id: 'open-model-picker',
      keys: { mac: ['Meta', 'k'], other: ['Control', 'k'] },
      description: 'Open model picker',
      scope: 'global',
      handler: openModelPicker,
    });
    keyboardShortcuts.register({
      id: 'switch-workspace',
      keys: { mac: ['Meta', 'j'], other: ['Control', 'j'] },
      description: 'Switch workspace',
      scope: 'global',
      handler: openWorkspaceSwitcher,
    });
    keyboardShortcuts.register({
      id: 'search-messages',
      keys: { mac: ['Meta', '/'], other: ['Control', '/'] },
      description: 'Search message history',
      scope: 'global',
      handler: focusMessageSearch,
    });
    keyboardShortcuts.register({
      id: 'new-chat',
      keys: { mac: ['Meta', 'n'], other: ['Control', 'n'] },
      description: 'Start new chat',
      scope: 'global',
      handler: startNewChat,
    });
    keyboardShortcuts.register({
      id: 'background-operation',
      keys: { mac: ['Meta', 'b'], other: ['Control', 'b'] },
      description: 'Background current agent operation',
      scope: 'global',
      handler: backgroundCurrent,
    });
    keyboardShortcuts.register({
      id: 'cancel-operation',
      keys: { mac: ['Meta', '.'], other: ['Control', '.'] },
      description: 'Cancel current agent operation',
      scope: 'global',
      handler: cancelCurrent,
    });
    keyboardShortcuts.register({
      // ⌘? — on most platforms '?' is Shift+/, so we require Shift in the
      // spec to be precise.
      id: 'show-shortcuts-help',
      keys: { mac: ['Meta', 'Shift', '?'], other: ['Control', 'Shift', '?'] },
      description: 'Show keyboard shortcuts help',
      scope: 'global',
      handler: toggleHelp,
    });

    const onKeyDown = (e: KeyboardEvent) => {
      keyboardShortcuts.dispatch(e);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      // Leave registrations in place so the help overlay (which may be
      // rendered by a parent in the future) still sees them. Components
      // that unmount truly should unregister; Chat lives for the app
      // lifetime so this is a noop in practice.
    };
  }, [
    openModelPicker,
    openWorkspaceSwitcher,
    focusMessageSearch,
    startNewChat,
    backgroundCurrent,
    cancelCurrent,
    toggleHelp,
  ]);

  // Calculate conversation stats
  const conversationStats = useMemo(() => {
    const turns = Math.floor(messages.length / 2);
    const tokens = messages.reduce((acc, msg) => acc + estimateTokens(msg.content), 0);
    return { turns, tokens };
  }, [messages]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Clear history when workspace changes
  useEffect(() => {
    if (workspace !== undefined) {
      setMessages([]);
    }
  }, [workspace]);

  const handleSend = async (content: string) => {
    // Add user message
    const userMessage: Message = { role: 'user', content };
    setMessages(prev => [...prev, userMessage]);
    setIsStreaming(true);

    // Create assistant message placeholder
    const assistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      const stream = chatStream({
        prompt: content,
        workspace,
        model,
        temperature,
        max_tokens: maxTokens,
        use_rag: useRag,
        rag_max_tokens: ragMaxTokens,
        history: messages,
        stream: true,
        thinking_effort: thinkingEffort,
        // includeSkills=true → undefined (use server-side auto-include)
        // includeSkills=false → empty array (explicit opt-out)
        additional_workspaces: includeSkills ? undefined : [],
      });

      for await (const chunk of stream) {
        setMessages(prev => {
          const updated = [...prev];
          const lastIndex = updated.length - 1;
          const lastMsg = updated[lastIndex];
          if (lastMsg.role === 'assistant') {
            // Create a new message object instead of mutating
            updated[lastIndex] = {
              ...lastMsg,
              content: lastMsg.content + chunk
            };
          }
          return updated;
        });
      }

      // Record this model in the server-side "recently used" list so the
      // ModelPicker can surface it under Recent on next open. Best-effort:
      // failure to record is silent (no user-facing error).
      if (model) {
        recordRecentModel(model).catch((err) => {
          console.warn('Failed to record recent model:', err);
        });
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => {
        const updated = [...prev];
        const lastIndex = updated.length - 1;
        const lastMsg = updated[lastIndex];
        if (lastMsg.role === 'assistant') {
          // Create a new message object instead of mutating
          updated[lastIndex] = {
            ...lastMsg,
            content: `Error: ${error instanceof Error ? error.message : 'Failed to get response'}`
          };
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  const handleClear = () => {
    setMessages([]);
  };

  // Filtered message list driven by the ⌘/ search input. When the search is
  // closed or the query is empty, we render every message (preserving stream
  // position). Otherwise we keep the indices stable by remembering the
  // original index alongside the message so each ChatMessage keeps a unique
  // key and the streaming placeholder logic below still works on the full
  // history.
  const filteredMessages = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!showSearch || q.length === 0) {
      return messages.map((m, i) => ({ message: m, originalIndex: i }));
    }
    return messages
      .map((m, i) => ({ message: m, originalIndex: i }))
      .filter(({ message }) => message.content.toLowerCase().includes(q));
  }, [messages, searchQuery, showSearch]);

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-gray-900">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            🤖 Ragbot
          </h1>
          {workspace && (
            <span className="text-sm text-gray-500 dark:text-gray-400">
              · {workspace}
            </span>
          )}
        </div>
        <button
          onClick={() => setShowSettings(!showSettings)}
          className={`px-3 py-1.5 text-sm rounded-lg transition-colors flex items-center gap-1
                     ${showSettings
                       ? 'bg-accent-light text-accent-dark dark:text-accent'
                       : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                     }`}
        >
          <span>{showSettings ? '▼' : '▶'}</span>
          Settings
        </button>
      </header>

      {/* Demo-mode banner (v3.2+) */}
      {demoMode && (
        <div
          role="status"
          className="px-4 py-2 bg-yellow-100 dark:bg-yellow-900/40 border-b border-yellow-300 dark:border-yellow-700 text-yellow-900 dark:text-yellow-200 text-sm"
        >
          <div className="max-w-6xl mx-auto flex items-center gap-2">
            <span>🎭</span>
            <span>
              <strong>Demo mode</strong> — running against bundled sample data,
              not your real workspaces. Unset <code className="font-mono">RAGBOT_DEMO</code> on the server to disable.
            </span>
          </div>
        </div>
      )}

      {/* Settings Panel */}
      {showSettings && (
        <SettingsPanel
          workspace={workspace}
          onWorkspaceChange={setWorkspace}
          model={model}
          onModelChange={setModel}
          temperature={temperature}
          onTemperatureChange={setTemperature}
          useRag={useRag}
          onUseRagChange={setUseRag}
          ragMaxTokens={ragMaxTokens}
          onRagMaxTokensChange={setRagMaxTokens}
          maxTokens={maxTokens}
          onMaxTokensChange={setMaxTokens}
          conversationTurns={conversationStats.turns}
          conversationTokens={conversationStats.tokens}
          onClearChat={handleClear}
          disabled={isStreaming}
          thinkingEffort={thinkingEffort}
          onThinkingEffortChange={setThinkingEffort}
          includeSkills={includeSkills}
          onIncludeSkillsChange={setIncludeSkills}
          openModelPickerSignal={openModelPickerSignal}
        />
      )}

      {/* Message-history search (⌘/). Hidden by default; toggled by shortcut. */}
      {showSearch && (
        <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
          <div className="max-w-3xl mx-auto flex items-center gap-2">
            <span className="text-sm text-gray-500 dark:text-gray-400">🔍</span>
            <input
              ref={searchInputRef}
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') {
                  e.preventDefault();
                  setShowSearch(false);
                  setSearchQuery('');
                }
              }}
              placeholder="Search message history..."
              aria-label="Search message history"
              data-shortcut-target="message-search"
              className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            />
            <button
              type="button"
              onClick={() => {
                setShowSearch(false);
                setSearchQuery('');
              }}
              className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 px-2 py-1"
              aria-label="Close search"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 dark:text-gray-400 mt-20">
              <div className="text-6xl mb-4">🤖</div>
              <p className="text-xl font-medium text-gray-700 dark:text-gray-300">Welcome to Ragbot</p>
              <p className="text-sm mt-2 max-w-md mx-auto">
                Your AI assistant with RAG-powered knowledge. Select a workspace above and start chatting.
              </p>
              {!workspace && (
                <p className="text-xs mt-4 text-amber-600 dark:text-amber-400">
                  ⚠️ Select a workspace to enable AI knowledge retrieval
                </p>
              )}
            </div>
          ) : filteredMessages.length === 0 ? (
            <div className="text-center text-gray-500 dark:text-gray-400 mt-20 text-sm">
              No messages match <span className="font-mono">&ldquo;{searchQuery}&rdquo;</span>.
            </div>
          ) : (
            filteredMessages.map(({ message, originalIndex }) => (
              <ChatMessage key={originalIndex} message={message} />
            ))
          )}
          {isStreaming && messages[messages.length - 1]?.content === '' && !showSearch && (
            <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 text-sm mt-4">
              <div className="flex gap-1">
                <span className="animate-bounce delay-0">●</span>
                <span className="animate-bounce delay-100">●</span>
                <span className="animate-bounce delay-200">●</span>
              </div>
              <span>Thinking...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <div className="max-w-3xl mx-auto">
          <ChatInput
            onSend={handleSend}
            disabled={isStreaming}
            placeholder={workspace ? `Message Ragbot about ${workspace}...` : 'Select a workspace to start chatting...'}
          />
        </div>
      </div>

      {/* Footer chrome — identifies Ragbot as the Synthesis Engineering
          reference runtime. The two domain links use the vermillion accent. */}
      <footer className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <div className="max-w-3xl mx-auto px-4 py-2 text-xs text-gray-500 dark:text-gray-400 text-center">
          Ragbot is by{' '}
          <strong className="font-semibold text-gray-700 dark:text-gray-300">
            Synthesis Engineering
          </strong>
          {' · '}
          <a
            href="https://synthesisengineering.org"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[color:var(--accent)] hover:text-[color:var(--accent-dark)] hover:underline"
          >
            synthesisengineering.org
          </a>
          {' · '}
          <a
            href="https://synthesiscoding.org"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[color:var(--accent)] hover:text-[color:var(--accent-dark)] hover:underline"
          >
            synthesiscoding.org
          </a>
          {' · MIT License'}
        </div>
      </footer>

      {/* Transient toast for shortcut feedback (⌘B / ⌘. / etc.). */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className={`fixed bottom-4 left-1/2 -translate-x-1/2 z-40 px-4 py-2 rounded-lg shadow-lg text-sm ${
            toast.tone === 'error'
              ? 'bg-red-600 text-white'
              : 'bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900'
          }`}
        >
          {toast.message}
        </div>
      )}

      {/* ⌘? help overlay. */}
      <ShortcutsHelpOverlay
        open={showShortcutsHelp}
        onClose={() => setShowShortcutsHelp(false)}
      />
    </div>
  );
}
