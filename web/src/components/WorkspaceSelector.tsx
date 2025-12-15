'use client';

import { useState, useEffect } from 'react';
import { getWorkspaces, WorkspaceInfo } from '@/lib/api';

interface WorkspaceSelectorProps {
  value: string | undefined;
  onChange: (workspace: string | undefined) => void;
  disabled?: boolean;
}

export function WorkspaceSelector({ value, onChange, disabled }: WorkspaceSelectorProps) {
  const [workspaces, setWorkspaces] = useState<WorkspaceInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadWorkspaces() {
      try {
        const data = await getWorkspaces();
        setWorkspaces(data);
        setError(null);
      } catch (e) {
        setError('Failed to load workspaces');
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    loadWorkspaces();
  }, []);

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-500 text-sm p-2 border border-red-300 rounded-lg">
        {error}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
        Workspace
      </label>
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value || undefined)}
        disabled={disabled}
        className="rounded-lg border border-gray-300 dark:border-gray-600
                   bg-white dark:bg-gray-800 px-3 py-2
                   text-gray-900 dark:text-gray-100
                   focus:outline-none focus:ring-2 focus:ring-blue-500
                   disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <option value="">Select a workspace...</option>
        {workspaces.map((ws) => (
          <option key={ws.dir_name} value={ws.dir_name}>
            {ws.name}
            {ws.description ? ` - ${ws.description}` : ''}
          </option>
        ))}
      </select>
      {value && (
        <WorkspaceStatus workspace={workspaces.find(w => w.dir_name === value)} />
      )}
    </div>
  );
}

function WorkspaceStatus({ workspace }: { workspace: WorkspaceInfo | undefined }) {
  if (!workspace) return null;

  const statusIcon = workspace.has_datasets ? '✅' : '⚠️';
  const statusText = workspace.has_datasets ? 'Ready for RAG' : 'No datasets';

  return (
    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-2">
      <span>{statusIcon}</span>
      <span>{statusText}</span>
      {workspace.has_instructions && <span className="text-green-600">• Instructions</span>}
    </div>
  );
}
