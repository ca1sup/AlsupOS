import React, { useEffect, useState } from 'react';
import { 
    HardDrive, DownloadCloud, Trash2, Check, RefreshCw, 
    Database, Activity, Search, AlertCircle, Cpu
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
    <div className="space-y-12 max-w-5xl animate-slide-up pb-20">
      
      {/* Header */}
      <div className="flex justify-between items-end border-b border-border-invisible pb-8">
        <div>
          <h2 className="text-3xl font-light text-txt-primary tracking-tight">Neural Engine</h2>
          <p className="text-txt-secondary mt-2 text-sm">Manage local inference models (MLX) and vector embeddings.</p>
        </div>
      </div>

      {/* 1. Active Configuration */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-6 bg-surface border border-border-subtle rounded-2xl relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                  <Cpu size={100} />
              </div>
              <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 bg-accent/10 rounded-lg text-accent"><Activity size={20} /></div>
                  <h3 className="text-sm font-bold uppercase tracking-widest text-txt-secondary">Active LLM</h3>
              </div>
              <div className="text-xl font-mono text-white mb-2 truncate max-w-[280px]" title={settings.llm_model}>
                  {settings.llm_model || 'Loading...'}
              </div>
              <p className="text-xs text-txt-tertiary">Used for Chat, Agents, and Summarization.</p>
          </div>

          <div className="p-6 bg-surface border border-border-subtle rounded-2xl relative overflow-hidden group opacity-75">
              <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                  <Database size={100} />
              </div>
              <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 bg-white/5 rounded-lg text-txt-secondary"><Search size={20} /></div>
                  <h3 className="text-sm font-bold uppercase tracking-widest text-txt-secondary">Embedding Model</h3>
              </div>
              <div className="text-lg font-mono text-txt-secondary mb-2 truncate">
                  nomic-embed-text-v1.5
              </div>
              <p className="text-xs text-txt-tertiary">Hardcoded for vector compatibility.</p>
          </div>
      </div>

      {/* 2. Download Hub */}
      <section className="space-y-6">
          <div className="flex items-center gap-3">
              <DownloadCloud className="text-accent" size={20} />
              <h3 className="text-xl font-light text-txt-primary">Download New Model</h3>
          </div>
          
          <div className="p-1 bg-gradient-to-r from-border-subtle to-transparent rounded-xl">
            <div className="bg-void rounded-xl p-1 flex gap-2">
                <input 
                    value={downloadInput}
                    onChange={(e) => setDownloadInput(e.target.value)}
                    placeholder="Hugging Face Repo ID (e.g. mlx-community/Phi-3-mini-4k-instruct)"
                    className="flex-1 bg-transparent border-none px-4 py-3 text-sm text-txt-primary placeholder-txt-tertiary focus:outline-none font-mono"
                />
                <button 
                    onClick={handlePull}
                    disabled={isDownloading || !downloadInput}
                    className="bg-accent hover:bg-white text-void px-6 py-2 rounded-lg font-bold text-xs uppercase tracking-wider transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                    {isDownloading ? <RefreshCw className="animate-spin" size={14}/> : <DownloadCloud size={14}/>}
                    {isDownloading ? "Queued" : "Pull"}
                </button>
            </div>
          </div>
          <div className="flex items-start gap-2 text-xs text-txt-tertiary px-2">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <p>Models are downloaded to <code>/backend/models</code>. Ensure you have sufficient disk space. Large models (70B+) may take a long time.</p>
          </div>
      </section>

      {/* 3. Local Library */}
      <section className="space-y-6">
          <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                  <HardDrive className="text-accent" size={20} />
                  <h3 className="text-xl font-light text-txt-primary">Local Library</h3>
              </div>
              <span className="text-xs font-mono text-txt-tertiary">{availableModels.length} Models Found</span>
          </div>

          <div className="grid grid-cols-1 gap-3">
              {availableModels.map((model: any) => {
                  const isActive = settings.llm_model === model.name;
                  const isDeleting = deletingId === model.name;

                  return (
                      <div 
                        key={model.name} 
                        className={cn(
                            "flex items-center justify-between p-4 rounded-xl border transition-all",
                            isActive 
                                ? "bg-accent/5 border-accent/20" 
                                : "bg-surface border-border-invisible hover:border-border-subtle"
                        )}
                      >
                          <div className="flex items-center gap-4 overflow-hidden">
                              <div className={cn(
                                  "w-10 h-10 rounded-lg flex items-center justify-center shrink-0",
                                  isActive ? "bg-accent text-void" : "bg-elevated text-txt-tertiary"
                              )}>
                                  {isActive ? <Check size={20} /> : <HardDrive size={20} />}
                              </div>
                              <div className="min-w-0">
                                  <h4 className="font-mono text-sm text-txt-primary truncate" title={model.name}>
                                      {model.name}
                                  </h4>
                                  <div className="flex items-center gap-3 text-xs text-txt-tertiary mt-1">
                                      <span>{model.size}</span>
                                      <span className="w-1 h-1 rounded-full bg-border-active" />
                                      <span>{model.source}</span>
                                  </div>
                              </div>
                          </div>

                          <div className="flex items-center gap-2 pl-4 shrink-0">
                              {!isActive && (
                                  <button 
                                    onClick={() => handleSetActive(model.name)}
                                    className="px-4 py-2 bg-elevated hover:bg-white/10 text-txt-secondary hover:text-white rounded-lg text-xs font-bold uppercase tracking-wider transition-colors"
                                  >
                                      Activate
                                  </button>
                              )}
                              
                              {/* Prevent deleting active model for safety */}
                              <button 
                                onClick={() => handleDelete(model.name)}
                                disabled={isActive || isDeleting}
                                className={cn(
                                    "p-2 rounded-lg transition-colors",
                                    isActive 
                                        ? "opacity-0 cursor-default" 
                                        : "text-txt-tertiary hover:bg-red-500/10 hover:text-red-500"
                                )}
                                title="Delete Model"
                              >
                                  {isDeleting ? <RefreshCw className="animate-spin" size={16} /> : <Trash2 size={16} />}
                              </button>
                          </div>
                      </div>
                  );
              })}

              {availableModels.length === 0 && (
                  <div className="text-center py-12 border-2 border-dashed border-border-invisible rounded-xl text-txt-tertiary">
                      No models found in library.
                  </div>
              )}
          </div>
      </section>

    </div>
  );
};

export default SettingsModels;