'use client';

import { useState, useEffect } from 'react';
import { getModels, type ModelInfo } from '@/lib/api';

interface ModelSelectorProps {
  value: string | undefined;
  onChange: (model: string | undefined) => void;
  disabled?: boolean;
}

export function ModelSelector({ value, onChange, disabled }: ModelSelectorProps) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [defaultModel, setDefaultModel] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadModels() {
      try {
        const data = await getModels();
        setModels(data.models);
        setDefaultModel(data.default_model);
        // Set default model if none selected
        if (!value && data.default_model) {
          onChange(data.default_model);
        }
        setError(null);
      } catch (e) {
        setError('Failed to load models');
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    loadModels();
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

  // Group models by provider
  const modelsByProvider = models.reduce((acc, model) => {
    if (!acc[model.provider]) {
      acc[model.provider] = [];
    }
    acc[model.provider].push(model);
    return acc;
  }, {} as Record<string, ModelInfo[]>);

  const providerLabels: Record<string, string> = {
    anthropic: 'Anthropic',
    openai: 'OpenAI',
    google: 'Google',
    aws_bedrock: 'AWS Bedrock',
  };

  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
        Model
      </label>
      <select
        value={value || defaultModel}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="rounded-lg border border-gray-300 dark:border-gray-600
                   bg-white dark:bg-gray-800 px-3 py-2
                   text-gray-900 dark:text-gray-100
                   focus:outline-none focus:ring-2 focus:ring-blue-500
                   disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {Object.entries(modelsByProvider).map(([provider, providerModels]) => (
          <optgroup key={provider} label={providerLabels[provider] || provider}>
            {providerModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name}
                {model.id === defaultModel ? ' (default)' : ''}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {value && <ModelDetails modelId={value} models={models} />}
    </div>
  );
}

function ModelDetails({ modelId, models }: { modelId: string; models: ModelInfo[] }) {
  const model = models.find(m => m.id === modelId);
  if (!model) return null;

  return (
    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-2">
      <span>{model.context_window.toLocaleString()} tokens</span>
      {model.supports_streaming && <span className="text-green-600">• Streaming</span>}
    </div>
  );
}
