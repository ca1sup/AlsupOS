import React, { useEffect, useState } from 'react';
import { Save, Loader2, HardDrive, RefreshCw, DownloadCloud } from 'lucide-react';
import { useAppStore } from '../../../store/useAppStore';
import { toast } from 'react-toastify';

const SettingsModels: React.FC = () => {
  const { settings, updateSettings, fetchInitialData } = useAppStore();
  const [localSettings, setLocalSettings] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Load
  useEffect(() => {
    const init = async () => {
        await fetchInitialData();
        setLoading(false);
    };
    init();
  }, [fetchInitialData]);

  // Sync
  useEffect(() => {
      if (settings) {
          setLocalSettings(settings);
      }
  }, [settings]);

  const handleChange = (key: string, val: string) => {
    setLocalSettings((prev: any) => ({ ...prev, [key]: val }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
        await updateSettings(localSettings);
        toast.success("Model Config Saved.");
    } catch (e) {
        toast.error("Save failed.");
        console.error(e);
    }
    setTimeout(() => setSaving(false), 500);
  };

  const handlePullModel = async () => {
      setDownloading(true);
      // Simulate or Trigger API pull if you implement that endpoint
      setTimeout(() => setDownloading(false), 2000);
  };

  if (loading) return <div className="p-12 text-txt-tertiary font-mono animate-pulse uppercase tracking-widest">Loading Model Registry...</div>;

  return (
    <div className="space-y-8 max-w-3xl animate-slide-up">
      <div className="flex justify-between items-end border-b border-border-invisible pb-8">
        <div>
          <h2 className="text-3xl font-light text-txt-primary tracking-tight">Model Registry</h2>
          <p className="text-txt-secondary mt-2 text-sm">Manage local inference models and endpoints.</p>
        </div>
        <button 
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-white text-void rounded-xl font-bold transition-all active:scale-95 disabled:opacity-50 shadow-glow uppercase tracking-widest text-xs"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save Configuration
        </button>
      </div>

      <div className="space-y-6">
        
        {/* Active Model Card */}
        <div className="p-8 bg-surface border border-border-invisible rounded-[24px] shadow-float">
            <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-elevated rounded-xl text-accent">
                    <HardDrive className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-light text-txt-primary">Active Model</h3>
            </div>
            
            <div className="space-y-6">
                <div>
                    <label className="block text-[11px] font-bold text-txt-tertiary uppercase tracking-widest mb-3">Model Identifier</label>
                    <div className="flex gap-3">
                        <input 
                            type="text" 
                            value={localSettings.llm_model || 'phi4-mini'}
                            onChange={e => handleChange('llm_model', e.target.value)}
                            className="flex-1 bg-input border border-border-subtle rounded-xl px-5 py-4 text-txt-primary focus:outline-none focus:border-accent transition-colors font-mono"
                        />
                        <button 
                            onClick={handlePullModel}
                            disabled={downloading}
                            className="bg-elevated hover:bg-border-active text-txt-primary px-6 rounded-xl flex items-center justify-center transition-colors disabled:opacity-50"
                            title="Pull Model"
                        >
                            {downloading ? <RefreshCw className="w-5 h-5 animate-spin" /> : <DownloadCloud className="w-5 h-5" />}
                        </button>
                    </div>
                    <p className="mt-3 text-xs text-txt-tertiary">Must match a supported MLX or Ollama model tag.</p>
                </div>
            </div>
        </div>

        {/* Embedding Model */}
        <div className="p-8 bg-surface border border-border-invisible rounded-[24px] shadow-sm opacity-60">
             <div className="flex items-center gap-4 mb-6">
                <div className="p-3 bg-elevated rounded-xl text-txt-secondary">
                    <HardDrive className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-light text-txt-primary">Embedding Model</h3>
            </div>
             <div>
                <label className="block text-[11px] font-bold text-txt-tertiary uppercase tracking-widest mb-3">Model Path</label>
                <input 
                    type="text" 
                    value={localSettings.embedding_model || 'nomic-ai/nomic-embed-text-v1.5'}
                    readOnly
                    className="w-full bg-input border border-border-subtle rounded-xl px-5 py-4 text-txt-secondary font-mono cursor-not-allowed"
                />
                <p className="mt-3 text-xs text-txt-tertiary">Embedding model is currently hardcoded for compatibility.</p>
            </div>
        </div>

      </div>
    </div>
  );
};

export default SettingsModels;