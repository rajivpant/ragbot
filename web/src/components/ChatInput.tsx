'use client';

import { useState, KeyboardEvent } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ onSend, disabled, placeholder = 'Type a message...' }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex gap-2 p-4 border-t border-gray-200 dark:border-gray-700">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        aria-label="Message composer"
        data-shortcut-target="composer"
        className="flex-1 resize-none rounded-lg border border-gray-300 dark:border-gray-600
                   bg-white dark:bg-gray-800 px-4 py-2
                   focus:outline-none focus:ring-2 focus:ring-accent
                   disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !input.trim()}
        className="px-4 py-2 bg-accent text-white rounded-lg
                   hover:bg-accent-dark disabled:opacity-50 disabled:cursor-not-allowed
                   transition-colors"
      >
        Send
      </button>
    </div>
  );
}
