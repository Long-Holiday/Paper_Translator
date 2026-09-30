import React, { useState, useEffect } from 'react';
import { X, Save, Key, Globe, Cpu, Loader2 } from 'lucide-react';
import { getTranslationConfig, updateTranslationConfig } from '../api/papers';
import { TranslationConfig } from '../types/paper';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const ConfigModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const [config, setConfig] = useState<TranslationConfig | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      setMsg('');
      setApiKeyInput('');
      getTranslationConfig()
        .then((cfg) => {
          setConfig(cfg);
        })
        .catch((err) => {
          setMsg(`加载配置失败: ${err.message}`);
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;
    setSaving(true);
    setMsg('');
    try {
      const payload: Partial<TranslationConfig> = {
        model: config.model,
        base_url: config.base_url,
        thread: Number(config.thread) || 1,
      };
      if (config.service) {
        payload.service = config.service;
      }
      if (apiKeyInput.trim()) {
        payload.api_key = apiKeyInput.trim();
      }
      await updateTranslationConfig(payload);
      setMsg('设置已成功保存！');
      setTimeout(() => {
        onClose();
      }, 800);
    } catch (err: any) {
      setMsg(`保存失败: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Globe className="w-5 h-5 text-sky-600" />
            翻译引擎设置
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {loading ? (
          <div className="p-12 flex justify-center items-center text-slate-500">
            <Loader2 className="w-6 h-6 animate-spin text-sky-600 mr-2" />
            正在加载配置...
          </div>
        ) : (
          <form onSubmit={handleSave} className="p-6 space-y-4">
            {msg && (
              <div className="p-3 text-sm rounded-lg bg-sky-50 text-sky-700 border border-sky-200">
                {msg}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">模型名称 (Model)</label>
              <input
                type="text"
                value={config?.model || ''}
                onChange={(e) => setConfig(prev => prev ? { ...prev, model: e.target.value } : null)}
                placeholder="例如 deepseek-chat 或 gpt-4o-mini"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">API 基础地址 (Base URL / OpenAI 兼容接口)</label>
              <input
                type="text"
                value={config?.base_url || ''}
                onChange={(e) => setConfig(prev => prev ? { ...prev, base_url: e.target.value } : null)}
                placeholder="例如 https://api.deepseek.com 或 https://api.openai.com/v1"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Key className="w-4 h-4 text-slate-500" />
                  API 密钥 (API Key)
                </span>
                {config?.api_key_masked && (
                  <span className="text-xs text-emerald-600 font-mono">已配置: {config.api_key_masked}</span>
                )}
              </label>
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder={config?.api_key_masked ? "留空则保持原密钥不变" : "请输入 API Key"}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:outline-none font-mono"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1 flex items-center gap-1">
                <Cpu className="w-4 h-4 text-slate-500" />
                并发线程数
              </label>
              <input
                type="number"
                min="1"
                max={config?.thread_limit || 16}
                value={config?.thread || 1}
                onChange={(e) => setConfig(prev => prev ? { ...prev, thread: parseInt(e.target.value) || 1 } : null)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:outline-none"
              />
            </div>

            <div className="pt-4 flex justify-end gap-3 border-t border-slate-100">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-sky-600 hover:bg-sky-700 rounded-lg transition-colors shadow-sm disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                保存设置
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
