'use client';

import { useState, useEffect } from 'react';
import { getModels, getWorkspaces, getIndexStatus, indexWorkspace, getConfig, getProviders, getTemperatureSettings, getKeysStatus, type ModelInfo, type WorkspaceInfo, type IndexStatus, type ProviderInfo, type KeysStatusResponse, type KeyStatus } from '@/lib/api';

interface SettingsPanelProps {
  workspace: string | undefined;
  onWorkspaceChange: (workspace: string | undefined) => void;
  model: string | undefined;
  onModelChange: (model: string | undefined) => void;
  temperature: number;
  onTemperatureChange: (temp: number) => void;
  useRag: boolean;
  onUseRagChange: (useRag: boolean) => void;
  ragMaxTokens: number;
  onRagMaxTokensChange: (tokens: number) => void;
  maxTokens: number;
  onMaxTokensChange: (tokens: number) => void;
  conversationTurns: number;
  conversationTokens: number;
  onClearChat: () => void;
  disabled?: boolean;
}

// Category labels - these are UI display names, not configuration
const CATEGORIES = ['small', 'medium', 'large', 'reasoning'];
const CATEGORY_LABELS: Record<string, string> = {
  small: 'Fast',
  medium: 'Balanced',
  large: 'Powerful',
  reasoning: 'Reasoning',
};

const MAX_TOKEN_OPTIONS = [256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536];

export function SettingsPanel({
  workspace,
  onWorkspaceChange,
  model,
  onModelChange,
  temperature,
  onTemperatureChange,
  useRag,
  onUseRagChange,
  ragMaxTokens,
  onRagMaxTokensChange,
  maxTokens,
  onMaxTokensChange,
  conversationTurns,
  conversationTokens,
  onClearChat,
  disabled,
}: SettingsPanelProps) {
  const [workspaces, setWorkspaces] = useState<WorkspaceInfo[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [temperaturePresets, setTemperaturePresets] = useState<Record<string, number>>({});
  const [defaultModel, setDefaultModel] = useState<string>('');
  const [keysStatus, setKeysStatus] = useState<KeysStatusResponse>({});
  const [workspacesWithKeys, setWorkspacesWithKeys] = useState<string[]>([]);
  const [indexStatus, setIndexStatus] = useState<IndexStatus | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Key source overrides - user can override workspace keys with default keys
  const [keyOverrides, setKeyOverrides] = useState<Record<string, 'auto' | 'default'>>({});

  // Derived state
  const [provider, setProvider] = useState<string>('anthropic');
  const [category, setCategory] = useState<string>('medium');

  // Load workspaces, models, providers, and config from API (all from engines.yaml)
  useEffect(() => {
    async function load() {
      try {
        const [wsData, modelData, configData, providersData, tempSettings] = await Promise.all([
          getWorkspaces(),
          getModels(),
          getConfig(),
          getProviders(),
          getTemperatureSettings(),
        ]);
        setWorkspaces(wsData);
        setModels(modelData.models);
        setDefaultModel(modelData.default_model);
        setWorkspacesWithKeys(configData.workspaces_with_keys || []);
        setProviders(providersData.providers);
        setTemperaturePresets(tempSettings);

        // Set default workspace if none selected and config has one
        const defaultWorkspaceName = configData.default_workspace;
        if (!workspace && defaultWorkspaceName) {
          const defaultWs = wsData.find(w => w.dir_name === defaultWorkspaceName || w.name.toLowerCase() === defaultWorkspaceName.toLowerCase());
          if (defaultWs) {
            onWorkspaceChange(defaultWs.dir_name);
          }
        }

        // Set default model if none selected
        if (!model && modelData.default_model) {
          onModelChange(modelData.default_model);
          // Parse provider from default model
          const defaultProvider = modelData.models.find(m => m.id === modelData.default_model)?.provider;
          if (defaultProvider) setProvider(defaultProvider);
        }
      } catch (e) {
        console.error('Failed to load settings data:', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Load keys status when workspace changes
  useEffect(() => {
    getKeysStatus(workspace)
      .then(setKeysStatus)
      .catch(() => setKeysStatus({}));

    // Reset key overrides when workspace changes
    setKeyOverrides({});
  }, [workspace]);

  // When keys status loads, ensure selected provider has a key; if not, switch to one that does
  useEffect(() => {
    if (Object.keys(keysStatus).length === 0) return; // Keys not loaded yet
    if (models.length === 0) return; // Models not loaded yet

    // Check if current provider has a key
    if (!keysStatus[provider]?.has_key) {
      // Find first provider with a key
      const providerWithKey = providers.find(p => keysStatus[p.id]?.has_key);
      if (providerWithKey) {
        // Inline provider change logic (can't call handleProviderChange as it's defined later)
        const newProvider = providerWithKey.id;
        setProvider(newProvider);
        const newProviderModels = models.filter(m => m.provider === newProvider);
        const newCategories = CATEGORIES.filter(cat =>
          newProviderModels.some(m => (m.category || 'medium') === cat)
        );
        const newCategory = newCategories.includes(category) ? category : newCategories[0] || 'medium';
        setCategory(newCategory);
        const newCategoryModels = newProviderModels.filter(m => (m.category || 'medium') === newCategory);
        if (newCategoryModels.length > 0) {
          onModelChange(newCategoryModels[0].id);
        }
      }
    }
  }, [keysStatus, providers, models]);

  // Load index status when workspace changes
  useEffect(() => {
    if (workspace) {
      getIndexStatus(workspace)
        .then(setIndexStatus)
        .catch(() => setIndexStatus(null));
    } else {
      setIndexStatus(null);
    }
  }, [workspace]);

  // Get effective key source for a provider (considering overrides)
  const getEffectiveKeySource = (providerId: string): KeyStatus['source'] => {
    const status = keysStatus[providerId];
    if (!status) return null;

    const override = keyOverrides[providerId];
    if (override === 'default' && status.has_default_key) {
      return 'default';
    }
    return status.source;
  };

  // Check if provider has any key available
  const hasKey = (providerId: string): boolean => {
    const status = keysStatus[providerId];
    return status?.has_key ?? false;
  };

  // Filter models by provider and category
  const providerModels = models.filter(m => m.provider === provider);
  const availableCategories = CATEGORIES.filter(cat =>
    providerModels.some(m => (m.category || 'medium') === cat)
  );
  const categoryModels = providerModels.filter(m =>
    (m.category || 'medium') === category
  );

  // When provider changes, update category and model
  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    const newProviderModels = models.filter(m => m.provider === newProvider);
    const newCategories = CATEGORIES.filter(cat =>
      newProviderModels.some(m => (m.category || 'medium') === cat)
    );
    const newCategory = newCategories.includes(category) ? category : newCategories[0] || 'medium';
    setCategory(newCategory);
    const newCategoryModels = newProviderModels.filter(m => (m.category || 'medium') === newCategory);
    if (newCategoryModels.length > 0) {
      onModelChange(newCategoryModels[0].id);
    }
  };

  // When category changes, update model
  const handleCategoryChange = (newCategory: string) => {
    setCategory(newCategory);
    const newCategoryModels = providerModels.filter(m => (m.category || 'medium') === newCategory);
    if (newCategoryModels.length > 0) {
      onModelChange(newCategoryModels[0].id);
    }
  };

  const handleIndex = async () => {
    if (!workspace) return;
    setIndexing(true);
    try {
      await indexWorkspace(workspace, true);
      const status = await getIndexStatus(workspace);
      setIndexStatus(status);
    } catch (e) {
      console.error('Indexing failed:', e);
    } finally {
      setIndexing(false);
    }
  };

  const selectedWorkspace = workspaces.find(w => w.dir_name === workspace);
  const selectedModel = models.find(m => m.id === model);

  if (loading) {
    return (
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
        <div className="animate-pulse flex gap-4">
          <div className="h-10 w-48 bg-gray-200 dark:bg-gray-700 rounded"></div>
          <div className="h-10 w-48 bg-gray-200 dark:bg-gray-700 rounded"></div>
          <div className="h-10 w-48 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
      {/* Main Settings Row */}
      <div className="px-4 py-3">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 max-w-6xl mx-auto">
          {/* Workspace */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Workspace
            </label>
            <select
              value={workspace || ''}
              onChange={(e) => onWorkspaceChange(e.target.value || undefined)}
              disabled={disabled}
              className="rounded-lg border border-gray-300 dark:border-gray-600
                         bg-white dark:bg-gray-800 px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select workspace...</option>
              {workspaces.map((ws) => (
                <option key={ws.dir_name} value={ws.dir_name}>
                  {ws.name}
                </option>
              ))}
            </select>
            {selectedWorkspace && (
              <div className="text-xs text-gray-500 flex items-center gap-1">
                {selectedWorkspace.has_datasets ? '✅' : '⚠️'}
                <span>{selectedWorkspace.has_datasets ? 'Has datasets' : 'No datasets'}</span>
                {selectedWorkspace.has_instructions && <span className="text-green-600">• Instructions</span>}
              </div>
            )}
          </div>

          {/* Provider & Model */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Model
            </label>
            <div className="flex gap-2">
              <select
                value={provider}
                onChange={(e) => handleProviderChange(e.target.value)}
                disabled={disabled}
                className="rounded-lg border border-gray-300 dark:border-gray-600
                           bg-white dark:bg-gray-800 px-2 py-2 text-sm w-28
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {providers.filter(p => hasKey(p.id)).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <select
                value={category}
                onChange={(e) => handleCategoryChange(e.target.value)}
                disabled={disabled}
                className="rounded-lg border border-gray-300 dark:border-gray-600
                           bg-white dark:bg-gray-800 px-2 py-2 text-sm flex-1
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {availableCategories.map((cat) => (
                  <option key={cat} value={cat}>
                    {CATEGORY_LABELS[cat]}
                  </option>
                ))}
              </select>
            </div>
            <select
              value={model || ''}
              onChange={(e) => onModelChange(e.target.value)}
              disabled={disabled}
              className="rounded-lg border border-gray-300 dark:border-gray-600
                         bg-white dark:bg-gray-800 px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {categoryModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            {selectedModel && (
              <div className="text-xs text-gray-500 flex items-center gap-1">
                {(selectedModel.context_window / 1000).toFixed(0)}K context
                <span className={getEffectiveKeySource(selectedModel.provider) === 'workspace' ? 'text-blue-600 ml-1' : 'text-gray-400 ml-1'}>
                  • {getEffectiveKeySource(selectedModel.provider)} key
                </span>
              </div>
            )}
          </div>

          {/* Temperature - presets from engines.yaml */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Creativity
            </label>
            <div className="flex gap-1">
              {Object.entries(temperaturePresets).map(([name, val]) => (
                <button
                  key={name}
                  onClick={() => onTemperatureChange(val)}
                  disabled={disabled}
                  className={`flex-1 px-2 py-2 text-xs rounded-lg border transition-colors capitalize
                    ${Math.abs(temperature - val) < 0.05
                      ? 'bg-blue-100 dark:bg-blue-900 border-blue-500 text-blue-700 dark:text-blue-300'
                      : 'border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700'
                    }`}
                >
                  {name}
                </button>
              ))}
            </div>
            <div className="text-xs text-gray-500 text-center">
              Temperature: {temperature.toFixed(2)}
            </div>
          </div>

          {/* Conversation Stats */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Conversation
            </label>
            <div className="flex gap-2 items-center">
              <div className="flex-1 bg-white dark:bg-gray-900 rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-center">
                <div className="text-lg font-semibold text-gray-900 dark:text-white">{conversationTurns}</div>
                <div className="text-xs text-gray-500">turns</div>
              </div>
              <div className="flex-1 bg-white dark:bg-gray-900 rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-center">
                <div className="text-lg font-semibold text-gray-900 dark:text-white">
                  {conversationTokens > 1000 ? `${(conversationTokens / 1000).toFixed(1)}K` : conversationTokens}
                </div>
                <div className="text-xs text-gray-500">tokens</div>
              </div>
              <button
                onClick={onClearChat}
                disabled={disabled || conversationTurns === 0}
                className="px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600
                           hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50
                           transition-colors"
                title="Clear chat"
              >
                🗑️
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* RAG Section */}
      <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">🔍 RAG</span>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={useRag}
                  onChange={(e) => onUseRagChange(e.target.checked)}
                  disabled={disabled || !selectedWorkspace?.has_datasets}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-600 dark:text-gray-400">Enable</span>
              </label>
            </div>

            {useRag && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Context:</span>
                <input
                  type="range"
                  min={500}
                  max={8000}
                  step={500}
                  value={ragMaxTokens}
                  onChange={(e) => onRagMaxTokensChange(Number(e.target.value))}
                  disabled={disabled}
                  className="w-24"
                />
                <span className="text-xs text-gray-600 dark:text-gray-400 w-16">{ragMaxTokens} tok</span>
              </div>
            )}

            {workspace && (
              <div className="flex items-center gap-2">
                {indexStatus?.indexed ? (
                  <span className="text-xs text-green-600">✅ {indexStatus.chunks || 0} chunks</span>
                ) : (
                  <span className="text-xs text-amber-600">⚠️ Not indexed</span>
                )}
                <button
                  onClick={handleIndex}
                  disabled={disabled || indexing}
                  className="px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600
                             hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
                >
                  {indexing ? '...' : indexStatus?.indexed ? '🔄 Rebuild' : '📚 Index'}
                </button>
              </div>
            )}

            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="ml-auto px-2 py-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            >
              {showAdvanced ? '▼ Advanced' : '▶ Advanced'}
            </button>
          </div>
        </div>
      </div>

      {/* Advanced Settings */}
      {showAdvanced && (
        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-900">
          <div className="max-w-6xl mx-auto">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-600 dark:text-gray-400">
                  Max Response Tokens
                </label>
                <select
                  value={maxTokens}
                  onChange={(e) => onMaxTokensChange(Number(e.target.value))}
                  disabled={disabled}
                  className="rounded border border-gray-300 dark:border-gray-600
                             bg-white dark:bg-gray-800 px-2 py-1 text-sm"
                >
                  {MAX_TOKEN_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt.toLocaleString()}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-600 dark:text-gray-400">
                  Model Info
                </label>
                <div className="text-xs text-gray-500 space-y-0.5">
                  <div>Provider: {providers.find(p => p.id === provider)?.name || provider}</div>
                  <div>Model: {selectedModel?.name || 'None'}</div>
                  <div>Context: {selectedModel ? `${(selectedModel.context_window / 1000).toFixed(0)}K` : '-'}</div>
                </div>
              </div>

              {/* API Keys with detailed status */}
              <div className="flex flex-col gap-1 md:col-span-2">
                <label className="text-xs font-medium text-gray-600 dark:text-gray-400">
                  API Keys for {workspace || 'default'}
                </label>
                <div className="bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 p-2">
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    {providers.map(p => {
                      const status = keysStatus[p.id];
                      const effectiveSource = getEffectiveKeySource(p.id);
                      const canOverride = status?.has_workspace_key && status?.has_default_key;

                      return (
                        <div key={p.id} className="flex flex-col gap-1">
                          <div className="flex items-center gap-1">
                            {status?.has_key ? (
                              <span className="text-green-600">✅</span>
                            ) : (
                              <span className="text-red-500">❌</span>
                            )}
                            <span className={status?.has_key ? 'text-gray-700 dark:text-gray-300' : 'text-gray-400'}>
                              {p.name}
                            </span>
                          </div>

                          {status?.has_key && (
                            <div className="flex items-center gap-1 pl-5">
                              <span className={`text-[10px] px-1 py-0.5 rounded ${
                                effectiveSource === 'workspace'
                                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                                  : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                              }`}>
                                {effectiveSource}
                              </span>

                              {canOverride && (
                                <button
                                  onClick={() => setKeyOverrides(prev => ({
                                    ...prev,
                                    [p.id]: prev[p.id] === 'default' ? 'auto' : 'default'
                                  }))}
                                  className="text-[10px] text-blue-600 hover:text-blue-800 dark:text-blue-400 ml-1"
                                  title={keyOverrides[p.id] === 'default' ? 'Use workspace key' : 'Use default key'}
                                >
                                  [{keyOverrides[p.id] === 'default' ? 'use workspace' : 'use default'}]
                                </button>
                              )}
                            </div>
                          )}

                          {!status?.has_key && (
                            <div className="text-[10px] text-gray-400 pl-5">
                              no key configured
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
