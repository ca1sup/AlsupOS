import { useState, useEffect } from 'react';
import { Trash2, Brain, RefreshCw, AlertCircle } from 'lucide-react';
import { toast } from 'react-toastify';
import { fetchUserFacts, deleteUserFact } from '../../../lib/api'; 

interface Fact {
  id: number;
  fact: string;
  created_at: string;
}

export function SettingsMemory() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadFacts = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await fetchUserFacts();
      setFacts(data);
    } catch (err: any) {
      console.error("Memory Load Error:", err);
      setError('Could not load memories.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if(!window.confirm("Delete this memory?")) return;
    try {
      await deleteUserFact(id);
      setFacts((prev) => prev.filter((f) => f.id !== id));
      toast.success('Memory deleted.');
    } catch (error) {
      toast.error('Failed to delete.');
    }
  };

  useEffect(() => {
    loadFacts();
  }, []);

  return (
    <div className="space-y-8 max-w-4xl animate-slide-up">
      <section className="bg-surface p-8 rounded-[24px] border border-border-invisible shadow-float">
        
        <div className="flex items-center justify-between mb-8 border-b border-border-invisible pb-6">
            <h3 className="text-xl font-light text-txt-primary flex items-center gap-3">
              <div className="p-2.5 bg-elevated rounded-xl text-accent"><Brain size={20} /></div>
              Long-Term Memory
            </h3>
            <button 
                onClick={loadFacts} 
                className="p-3 text-txt-secondary hover:text-txt-primary hover:bg-elevated rounded-xl transition-colors active:scale-95"
                title="Refresh"
            >
                <RefreshCw size={18} className={isLoading ? "animate-spin" : ""} />
            </button>
        </div>
        
        <p className="text-sm text-txt-secondary mb-8 leading-relaxed max-w-2xl">
          Facts the AI has learned from your conversations. Deleted memories cannot be recovered.
        </p>

        {error && (
          <div className="p-4 mb-6 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm flex items-center gap-2">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {isLoading && facts.length === 0 ? (
          <div className="text-center py-12 text-txt-tertiary animate-pulse font-mono text-xs uppercase tracking-widest">Scanning neural pathways...</div>
        ) : facts.length === 0 ? (
          <div className="text-center py-12 text-txt-tertiary italic bg-input/30 rounded-2xl border border-border-invisible border-dashed">
            No memories stored yet.
          </div>
        ) : (
          <div className="space-y-3">
            {facts.map((fact) => (
              <div
                key={fact.id}
                className="flex items-start justify-between p-5 bg-elevated/30 rounded-2xl border border-border-invisible group hover:border-accent/30 transition-all duration-300"
              >
                <div className="flex-1 pr-6">
                  <p className="text-sm text-txt-body leading-relaxed">{fact.fact}</p>
                  <p className="text-[10px] text-txt-tertiary mt-2 uppercase tracking-wide font-bold">
                    Learned {new Date(fact.created_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  onClick={() => handleDelete(fact.id)}
                  className="p-2.5 text-txt-tertiary hover:text-red-500 hover:bg-void rounded-xl transition-colors opacity-0 group-hover:opacity-100"
                  title="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}