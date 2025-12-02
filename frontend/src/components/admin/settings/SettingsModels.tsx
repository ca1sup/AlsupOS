import React, { useEffect, useState } from 'react';
import { 
    HardDrive, DownloadCloud, Trash2, Check, RefreshCw, 
    Database, Activity, AlertCircle, Cpu
} from 'lucide-react';
import { useAppStore } from '../../../store/useAppStore';
import { toast } from 'react-toastify';
import { cn } from '../../../lib/utils';

const SettingsModels: React.FC = () => {
  const { 
      settings, 
      availableModels, 
      fetchModels, 
      deleteModel, 
      pullModel,
      updateSettings 
  } = useAppStore();

  const [downloadInput, setDownloadInput] = useState('');
  const [isDownloading, setIsDownloading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
      fetchModels();
      const interval = setInterval(fetchModels, 5000);
      return () => clearInterval(interval);
  }, []);

  const handlePull = async () => {
      if (!downloadInput.trim()) return;
      setIsDownloading(true);
      try {
          await pullModel(downloadInput);
          toast.info(`Started download: ${downloadInput}`);
          setDownloadInput('');
      } catch (e) {
          toast.error("Failed to start download.");
      }
      setTimeout(() => setIsDownloading(false), 2000);
  };

  const handleDelete = async (id: string) => {
      if (!confirm(`Permanently delete ${id}?`)) return;
      setDeletingId(id);
      try {
          await deleteModel(id);
          toast.success("Model deleted.");
      } catch (e) {
          toast.error("Failed to delete model.");
      } finally {
          setDeletingId(null);
      }
  };

  const handleSetActive = async (id: string) => {
      await updateSettings({ ...settings, llm_model: id });
      toast.success(`Active model set to: ${id}`);
  };

  return (
    <div className="space-y-10 max-w-4xl animate-slide-up pb-20">
      
      {/* Header */}
      <div className="border-b border-border-invisible pb-6">
        <h2 className="text-2xl font-light text-txt-primary tracking-tight">Neural Engine</h2>
        <p className="text-txt-secondary mt-1 text-sm">Manage local inference models and embeddings.</p>
      </div>

      {/* 1. Active Configuration */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-5 bg-surface border border-border-subtle rounded-xl flex flex-col justify-between">
              <div className="flex items-center gap-2 mb-3">
                  <Activity size={16} className="text-accent" />
                  <h3 className="text-xs font-bold uppercase tracking-widest text-txt-tertiary">Active LLM</h3>
              </div>
              <div className="text-base font-mono text-txt-primary mb-1 break-all">
                  {settings.llm_model || 'Loading...'}
              </div>
              <p className="text-xs text-txt-tertiary">Used for Chat & Agents</p>
          </div>

          <div className="p-5 bg-surface border border-border-subtle rounded-xl flex flex-col justify-between opacity-80">
              <div className="flex items-center gap-2 mb-3">
                  <Database size={16} className="text-txt-tertiary" />
                  <h3 className="text-xs font-bold uppercase tracking-widest text-txt-tertiary">Embedding Model</h3>
              </div>
              <div className="text-base font-mono text-txt-secondary mb-1">
                  nomic-embed-text-v1.5
              </div>
              <p className="text-xs text-txt-tertiary">Vector Database Core</p>
          </div>
      </div>

      {/* 2. Download Hub */}
      <section className="space-y-4">
          <div className="flex items-center gap-2">
              <DownloadCloud className="text-txt-secondary" size={18} />
              <h3 className="text-lg font-light text-txt-primary">Download Model</h3>
          </div>
          
          <div className="bg-surface border border-border-subtle rounded-lg p-1 flex gap-2">
                <input 
                    value={downloadInput}
                    onChange={(e) => setDownloadInput(e.target.value)}
                    placeholder="Hugging Face Repo ID (e.g. mlx-community/Phi-3...)"
                    className="flex-1 bg-transparent border-none px-3 py-2 text-sm text-txt-primary placeholder-txt-tertiary focus:outline-none font-mono"
                />
                <button 
                    onClick={handlePull}
                    disabled={isDownloading || !downloadInput}
                    className="bg-elevated hover:bg-accent hover:text-white text-txt-secondary px-4 py-2 rounded text-xs font-bold uppercase tracking-wide transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                    {isDownloading ? <RefreshCw className="animate-spin" size={14}/> : <DownloadCloud size={14}/>}
                    {isDownloading ? "Queued" : "Pull"}
                </button>
          </div>
          <div className="flex items-start gap-2 text-xs text-txt-tertiary px-1">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <p>Models download to <code>/backend/models</code>. Large models (70B+) may take time.</p>
          </div>
      </section>

      {/* 3. Local Library */}
      <section className="space-y-4">
          <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                  <HardDrive className="text-txt-secondary" size={18} />
                  <h3 className="text-lg font-light text-txt-primary">Library</h3>
              </div>
              <span className="text-xs font-mono text-txt-tertiary">{availableModels.length} Installed</span>
          </div>

          <div className="flex flex-col gap-2">
              {availableModels.map((model: any) => {
                  const isActive = settings.llm_model === model.name;
                  const isDeleting = deletingId === model.name;

                  return (
                      <div 
                        key={model.name} 
                        className={cn(
                            "flex items-center justify-between p-3 rounded-lg border transition-all",
                            isActive 
                                ? "bg-accent/5 border-accent/30" 
                                : "bg-surface border-border-invisible hover:border-border-subtle"
                        )}
                      >
                          <div className="flex items-center gap-3 overflow-hidden pr-4">
                              <div className={cn(
                                  "w-8 h-8 rounded flex items-center justify-center shrink-0",
                                  isActive ? "bg-accent text-white" : "bg-elevated text-txt-tertiary"
                              )}>
                                  {isActive ? <Check size={16} /> : <Cpu size={16} />}
                              </div>
                              <div className="min-w-0">
                                  <h4 className="font-mono text-sm text-txt-primary break-all leading-tight" title={model.name}>
                                      {model.name}
                                  </h4>
                                  <div className="flex items-center gap-2 text-xs text-txt-tertiary mt-0.5">
                                      <span>{model.size}</span>
                                      <span className="opacity-30">•</span>
                                      <span>{model.source}</span>
                                  </div>
                              </div>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                              {!isActive && (
                                  <button 
                                    onClick={() => handleSetActive(model.name)}
                                    className="px-3 py-1.5 bg-elevated hover:bg-white/10 text-txt-secondary hover:text-white rounded text-xs font-bold uppercase tracking-wide transition-colors"
                                  >
                                      Load
                                  </button>
                              )}
                              
                              <button 
                                onClick={() => handleDelete(model.name)}
                                disabled={isActive || isDeleting}
                                className={cn(
                                    "p-1.5 rounded transition-colors",
                                    isActive 
                                        ? "opacity-0 cursor-default" 
                                        : "text-txt-tertiary hover:bg-red-500/10 hover:text-red-500"
                                )}
                                title="Delete Model"
                              >
                                  {isDeleting ? <RefreshCw className="animate-spin" size={14} /> : <Trash2 size={14} />}
                              </button>
                          </div>
                      </div>
                  );
              })}

              {availableModels.length === 0 && (
                  <div className="text-center py-10 border border-dashed border-border-subtle rounded-lg text-txt-tertiary text-sm">
                      No models found in library.
                  </div>
              )}
          </div>
      </section>

    </div>
  );
};

export default SettingsModels;