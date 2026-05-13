'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { Message, chatStream, getConfig, recordRecentModel, type ThinkingEffort } from '@/lib/api';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { SettingsPanel } from './SettingsPanel';

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

  // ⌘K / Ctrl+K opens the ModelPicker imperatively, except when the user
  // is typing into a text field (let the browser/component handle it there).
  useEffect(() => {
    const isTextTarget = (el: EventTarget | null) => {
      if (!(el instanceof HTMLElement)) return false;
      const tag = el.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return true;
      if (el.isContentEditable) return true;
      return false;
    };
    const onKeyDown = (e: KeyboardEvent) => {
      const isShortcut = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k';
      if (!isShortcut) return;
      if (isTextTarget(e.target)) return;
      e.preventDefault();
      setOpenModelPickerSignal((n) => n + 1);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

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
                       ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
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
          ) : (
            messages.map((message, index) => (
              <ChatMessage key={index} message={message} />
            ))
          )}
          {isStreaming && messages[messages.length - 1]?.content === '' && (
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
    </div>
  );
}
