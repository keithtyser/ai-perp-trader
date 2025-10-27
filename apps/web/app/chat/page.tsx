'use client';

import useSWR from 'swr';
import { api } from '@/lib/api';
import { useState } from 'react';

export default function ChatPage() {
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);

  const { data: messages, error } = useSWR(
    ['chat', limit, offset],
    () => api.getChat(limit, offset),
    { refreshInterval: 30000 }
  );

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            MODELCHAT
          </h2>
        </div>
        <div>
          <select className="bg-gray-900 text-white px-4 py-2 rounded border border-gray-700">
            <option>ALL MODELS</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-4 rounded">
          Failed to load chat messages
        </div>
      )}

      {!messages && !error && (
        <div className="text-gray-500">Loading messages...</div>
      )}

      {messages && messages.length === 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-12 text-center text-gray-500">
          No messages yet
        </div>
      )}

      {messages && messages.length > 0 && (
        <>
          <div className="space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className="bg-white dark:bg-gray-800 rounded-lg border-l-4 border-emerald-500 p-6 shadow-sm"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full bg-emerald-500 flex items-center justify-center text-white flex-shrink-0">
                    <span className="text-2xl">◎</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="font-bold text-lg text-emerald-600 dark:text-emerald-400">
                        KEITH'S CRYPTO AGENT
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {new Date(msg.ts).toLocaleString()}
                      </div>
                    </div>
                    <div className="text-gray-700 dark:text-gray-300 leading-relaxed">
                      {msg.content}
                    </div>
                    <div className="mt-3 text-right">
                      <button className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                        click to expand
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          <div className="flex justify-between items-center pt-4">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="px-4 py-2 bg-gray-900 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed border border-gray-700"
            >
              Previous
            </button>
            <span className="text-gray-600 dark:text-gray-400">
              Showing {offset + 1} - {offset + messages.length}
            </span>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={messages.length < limit}
              className="px-4 py-2 bg-gray-900 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed border border-gray-700"
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
