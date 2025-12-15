'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter, SyntaxHighlighterProps } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Message } from '@/lib/api';

interface ChatMessageProps {
  message: Message;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-md
                 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
      title="Copy to clipboard"
    >
      {copied ? (
        <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      )}
    </button>
  );
}

function CodeCopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded-md bg-gray-700 hover:bg-gray-600
                 text-gray-300 hover:text-white transition-colors text-xs"
      title="Copy code"
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[80%] rounded-2xl px-4 py-2.5 bg-blue-600 text-white">
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-4 group">
      <div className="max-w-[85%] rounded-2xl px-4 py-3 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 relative">
        <div className="absolute -top-2 -right-2">
          <CopyButton text={message.content} />
        </div>
        <div className="prose prose-sm dark:prose-invert max-w-none
                        prose-headings:mt-3 prose-headings:mb-2 prose-headings:font-semibold
                        prose-h1:text-xl prose-h2:text-lg prose-h3:text-base
                        prose-p:my-2 prose-p:leading-relaxed
                        prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5
                        prose-code:text-pink-500 dark:prose-code:text-pink-400
                        prose-code:bg-gray-200 dark:prose-code:bg-gray-700
                        prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-sm
                        prose-pre:my-3 prose-pre:p-0 prose-pre:bg-transparent
                        prose-a:text-blue-600 dark:prose-a:text-blue-400
                        prose-strong:font-semibold
                        prose-blockquote:border-l-blue-500 prose-blockquote:bg-blue-50 dark:prose-blockquote:bg-blue-900/20
                        prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:rounded-r">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                const codeString = String(children).replace(/\n$/, '');

                if (match) {
                  return (
                    <div className="relative group/code">
                      <CodeCopyButton code={codeString} />
                      <SyntaxHighlighter
                        style={oneDark as SyntaxHighlighterProps['style']}
                        language={match[1]}
                        PreTag="div"
                        className="rounded-lg !my-0"
                      >
                        {codeString}
                      </SyntaxHighlighter>
                    </div>
                  );
                }

                return (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
              table({ children }) {
                return (
                  <div className="overflow-x-auto my-3">
                    <table className="min-w-full border-collapse border border-gray-300 dark:border-gray-600">
                      {children}
                    </table>
                  </div>
                );
              },
              th({ children }) {
                return (
                  <th className="border border-gray-300 dark:border-gray-600 px-3 py-2 bg-gray-200 dark:bg-gray-700 font-semibold text-left">
                    {children}
                  </th>
                );
              },
              td({ children }) {
                return (
                  <td className="border border-gray-300 dark:border-gray-600 px-3 py-2">
                    {children}
                  </td>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
