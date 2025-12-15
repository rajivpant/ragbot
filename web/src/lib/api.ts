/**
 * API client for Ragbot FastAPI backend
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Types
export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatRequest {
  prompt: string;
  workspace?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  use_rag?: boolean;
  rag_max_tokens?: number;
  history?: Message[];
  stream?: boolean;
}

export interface WorkspaceInfo {
  name: string;
  dir_name: string;
  description?: string;
  status: string;
  type: string;
  inherits_from: string[];
  has_instructions: boolean;
  has_datasets: boolean;
  has_source: boolean;
  repo_path?: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  context_window: number;
  supports_streaming: boolean;
  supports_system_role: boolean;
  available?: boolean;
  category?: string;
  max_output_tokens?: number;
  temperature?: number;
  max_temperature?: number;
}

export interface ConfigResponse {
  version: string;
  ai_knowledge_root?: string;
  workspace_count: number;
  rag_available: boolean;
  default_model: string;
  default_workspace?: string;
  api_keys: Record<string, boolean>;
  workspaces_with_keys: string[];
}

// API functions
export async function getConfig(): Promise<ConfigResponse> {
  const res = await fetch(`${API_BASE}/api/config`);
  if (!res.ok) throw new Error('Failed to fetch config');
  return res.json();
}

export async function getWorkspaces(): Promise<WorkspaceInfo[]> {
  const res = await fetch(`${API_BASE}/api/workspaces`);
  if (!res.ok) throw new Error('Failed to fetch workspaces');
  const data = await res.json();
  return data.workspaces;
}

export async function getModels(): Promise<{ models: ModelInfo[]; default_model: string; api_keys_configured?: Record<string, boolean> }> {
  // Use /api/models/all to get all models regardless of API key status
  const res = await fetch(`${API_BASE}/api/models/all`);
  if (!res.ok) throw new Error('Failed to fetch models');
  return res.json();
}

export interface ProviderInfo {
  id: string;
  name: string;
}

export async function getProviders(): Promise<{ providers: ProviderInfo[] }> {
  const res = await fetch(`${API_BASE}/api/models/providers`);
  if (!res.ok) throw new Error('Failed to fetch providers');
  return res.json();
}

export async function getTemperatureSettings(): Promise<Record<string, number>> {
  const res = await fetch(`${API_BASE}/api/models/temperature-settings`);
  if (!res.ok) throw new Error('Failed to fetch temperature settings');
  return res.json();
}

export interface IndexStatus {
  indexed: boolean;
  collection_name?: string;
  chunks?: number;
  error?: string;
}

export async function getIndexStatus(workspace: string): Promise<IndexStatus> {
  const res = await fetch(`${API_BASE}/api/workspaces/${workspace}/index`);
  if (!res.ok) throw new Error('Failed to get index status');
  return res.json();
}

export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Send a chat message and stream the response
 */
export async function* chatStream(request: ChatRequest): AsyncGenerator<string> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    body: JSON.stringify({
      ...request,
      stream: true,
    }),
  });

  if (!res.ok) {
    throw new Error(`Chat failed: ${res.statusText}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') return;

        try {
          const parsed = JSON.parse(data);
          if (parsed.content) {
            yield parsed.content;
          }
          if (parsed.error) {
            throw new Error(parsed.error);
          }
        } catch (e) {
          // Skip non-JSON data
        }
      }
    }
  }
}

/**
 * Send a chat message without streaming
 */
export async function chat(request: ChatRequest): Promise<string> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      ...request,
      stream: false,
    }),
  });

  if (!res.ok) {
    throw new Error(`Chat failed: ${res.statusText}`);
  }

  const data = await res.json();
  return data.response;
}

/**
 * Trigger workspace indexing
 */
export async function indexWorkspace(name: string, force = false): Promise<void> {
  const res = await fetch(`${API_BASE}/api/workspaces/${name}/index`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ force }),
  });

  if (!res.ok) {
    throw new Error(`Indexing failed: ${res.statusText}`);
  }
}
