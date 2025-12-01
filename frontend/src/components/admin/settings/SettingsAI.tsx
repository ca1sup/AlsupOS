import React, { useEffect, useState } from 'react';
import { Save, Loader2, Brain, Activity, Stethoscope, Users, BookOpen } from 'lucide-react';
import { toast } from 'react-toastify';
import { cn } from '../../../lib/utils';
import { useAppStore } from '../../../store/useAppStore';

// Helper for Tabs
const TabButton = ({ active, onClick, icon: Icon, label }: any) => (
  <button
    onClick={onClick}
    className={cn(
      "flex items-center gap-2 px-6 py-4 text-xs font-bold uppercase tracking-widest transition-all border-b-2",
      active 
        ? "border-accent text-accent bg-surface" 
        : "border-transparent text-txt-tertiary hover:text-txt-primary hover:bg-surface/50"
    )}
  >
    <Icon size={16} />
    <span className="hidden md:inline">{label}</span>
  </button>
);

const SettingsAI: React.FC = () => {
  const { settings, updateSettings, fetchInitialData } = useAppStore();
  const [localSettings, setLocalSettings] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('clinical');

  // Load initial data from store
  useEffect(() => {
    const init = async () => {
        await fetchInitialData();
        setLoading(false);
    };
    init();
  }, [fetchInitialData]);

  // Sync local state when store updates
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
      toast.success("Neural Configuration Saved.");
    } catch (e) {
      console.error(e);
      toast.error("Save failed.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-12 text-txt-tertiary font-mono animate-pulse uppercase tracking-widest">Loading Neural Config...</div>;

  return (
    <div className="space-y-8 max-w-5xl animate-slide-up pb-32">
      
      {/* Header */}
      <div className="flex justify-between items-end border-b border-border-invisible pb-8">
        <div>
          <h2 className="text-3xl font-light text-txt-primary tracking-tight">Brain & Prompts</h2>
          <p className="text-txt-secondary mt-2 text-sm">Configure the personality and reasoning engines.</p>
        </div>
        <button 
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-white text-void rounded-xl font-bold transition-all active:scale-95 disabled:opacity-50 shadow-glow uppercase tracking-widest text-xs"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Update Brain
        </button>
      </div>

      {/* Tabs */}
      <div className="flex overflow-x-auto border-b border-border-invisible bg-elevated/20 rounded-t-[24px]">
          <TabButton active={activeTab === 'clinical'} onClick={() => setActiveTab('clinical')} icon={Stethoscope} label="Clinical" />
          <TabButton active={activeTab === 'steward'} onClick={() => setActiveTab('steward')} icon={Activity} label="Steward" />
          <TabButton active={activeTab === 'experts'} onClick={() => setActiveTab('experts')} icon={Brain} label="Experts" />
          <TabButton active={activeTab === 'family'} onClick={() => setActiveTab('family')} icon={Users} label="Family" />
          <TabButton active={activeTab === 'research'} onClick={() => setActiveTab('research')} icon={BookOpen} label="Research" />
      </div>

      {/* Content Area */}
      <div className="bg-surface border-x border-b border-border-invisible rounded-b-[24px] p-8 shadow-float min-h-[500px]">
        
        {/* 1. CLINICAL */}
        {activeTab === 'clinical' && (
            <div className="space-y-8">
                <div>
                    <h3 className="text-xl font-light text-txt-primary mb-3">Master Chart Template</h3>
                    <p className="text-xs text-txt-tertiary mb-4">The Markdown structure enforced by the Scribe.</p>
                    <textarea 
                        rows={15}
                        value={localSettings.er_master_chart_template || ''}
                        onChange={e => handleChange('er_master_chart_template', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body font-mono text-xs leading-relaxed focus:border-accent outline-none"
                    />
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <div>
                        <h3 className="text-[10px] font-bold text-accent uppercase tracking-widest mb-3">System: Scribe</h3>
                        <textarea 
                            rows={10}
                            value={localSettings.er_system_scribe || ''}
                            onChange={e => handleChange('er_system_scribe', e.target.value)}
                            className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body text-sm focus:border-accent outline-none"
                        />
                    </div>
                    <div>
                        <h3 className="text-[10px] font-bold text-accent uppercase tracking-widest mb-3">System: Attending</h3>
                        <textarea 
                            rows={10}
                            value={localSettings.er_system_attending || ''}
                            onChange={e => handleChange('er_system_attending', e.target.value)}
                            className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body text-sm focus:border-accent outline-none"
                        />
                    </div>
                </div>
            </div>
        )}

        {/* 2. STEWARD */}
        {activeTab === 'steward' && (
            <div className="space-y-6">
                <div>
                    <h3 className="text-xl font-light text-txt-primary mb-3">Daily Briefing Logic</h3>
                    <p className="text-xs text-txt-tertiary mb-4">Controls the Morning Briefing structure. Use {'{curly_braces}'} for data injection.</p>
                    <textarea 
                        rows={20}
                        value={localSettings.steward_daily_prompt_template || ''}
                        onChange={e => handleChange('steward_daily_prompt_template', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body font-mono text-sm leading-relaxed focus:border-accent outline-none"
                    />
                </div>
            </div>
        )}

        {/* 3. EXPERTS */}
        {activeTab === 'experts' && (
            <div className="grid grid-cols-1 gap-10">
                <div>
                    <h3 className="text-[10px] font-bold text-accent uppercase tracking-widest mb-3">Finance Advisor</h3>
                    <textarea 
                        rows={6}
                        value={localSettings.steward_finance_prompt || ''}
                        onChange={e => handleChange('steward_finance_prompt', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body text-sm focus:border-accent outline-none"
                    />
                </div>
                <div>
                    <h3 className="text-[10px] font-bold text-accent uppercase tracking-widest mb-3">Health Coach</h3>
                    <textarea 
                        rows={6}
                        value={localSettings.steward_health_prompt || ''}
                        onChange={e => handleChange('steward_health_prompt', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body text-sm focus:border-accent outline-none"
                    />
                </div>
                <div>
                    <h3 className="text-[10px] font-bold text-accent uppercase tracking-widest mb-3">Workout Trainer</h3>
                    <textarea 
                        rows={6}
                        value={localSettings.steward_workout_prompt || ''}
                        onChange={e => handleChange('steward_workout_prompt', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body text-sm focus:border-accent outline-none"
                    />
                </div>
            </div>
        )}

        {/* 4. FAMILY */}
        {activeTab === 'family' && (
            <div className="space-y-10">
                <div>
                    <h3 className="text-xl font-light text-txt-primary mb-3">Theological Simplifier</h3>
                    <p className="text-xs text-txt-tertiary mb-3">Instructions for explaining concepts to children.</p>
                    <textarea 
                        rows={6}
                        value={localSettings.worship_simplify_prompt || ''}
                        onChange={e => handleChange('worship_simplify_prompt', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body text-sm focus:border-accent outline-none"
                    />
                </div>
                <div>
                    <h3 className="text-xl font-light text-txt-primary mb-3">Meal Planner</h3>
                    <p className="text-xs text-txt-tertiary mb-3">Logic for generating grocery lists from pantry items.</p>
                    <textarea 
                        rows={10}
                        value={localSettings.mealplan_generation_prompt || ''}
                        onChange={e => handleChange('mealplan_generation_prompt', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body text-sm focus:border-accent outline-none"
                    />
                </div>
            </div>
        )}

        {/* 5. RESEARCH */}
        {activeTab === 'research' && (
            <div className="space-y-10">
                <div>
                    <h3 className="text-xl font-light text-txt-primary mb-3">Clinical Refresher</h3>
                    <p className="text-xs text-txt-tertiary mb-3">Prompt for generating board-review style pearls.</p>
                    <textarea 
                        rows={6}
                        value={localSettings.med_news_refresher_prompt || ''}
                        onChange={e => handleChange('med_news_refresher_prompt', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body text-sm focus:border-accent outline-none"
                    />
                </div>
                <div>
                    <h3 className="text-xl font-light text-txt-primary mb-3">Article Summarizer</h3>
                    <p className="text-xs text-txt-tertiary mb-3">Prompt for condensing RSS feeds.</p>
                    <textarea 
                        rows={6}
                        value={localSettings.med_news_summary_prompt || ''}
                        onChange={e => handleChange('med_news_summary_prompt', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl p-5 text-txt-body text-sm focus:border-accent outline-none"
                    />
                </div>
            </div>
        )}

      </div>
    </div>
  );
};

export { SettingsAI };