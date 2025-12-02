import React, { useEffect, useState } from 'react';
import { Save, Loader2, MapPin, User, Mic } from 'lucide-react';
import { toast } from 'react-toastify';
import { useAppStore } from '../../../store/useAppStore';

const SettingsGeneral: React.FC = () => {
  const { settings, updateSettings, fetchInitialData } = useAppStore();
  const [localSettings, setLocalSettings] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const init = async () => {
        await fetchInitialData();
        setLoading(false);
    };
    init();
  }, [fetchInitialData]);

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
      toast.success("Settings saved");
    } catch (e) {
      console.error(e);
      toast.error("Error saving");
    } finally {
      setTimeout(() => setSaving(false), 500);
    }
  };

  if (loading) return <div className="p-8 text-txt-tertiary font-mono animate-pulse">Loading configuration...</div>;

  return (
    <div className="space-y-12 max-w-3xl animate-slide-up">
      <div className="flex justify-between items-end border-b border-border-invisible pb-8">
        <div>
          <h2 className="text-3xl font-light text-txt-primary">General Configuration</h2>
          <p className="text-txt-secondary mt-2 text-sm">Core system identity and location preferences.</p>
        </div>
        <button 
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-3 bg-accent hover:bg-white text-void rounded-xl font-bold transition-all active:scale-95 disabled:opacity-50 shadow-glow"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save Changes
        </button>
      </div>

      <div className="space-y-8">
        
        {/* Identity Section */}
        <div className="p-8 bg-surface border border-border-invisible hover:border-border-subtle rounded-[24px] transition-colors">
            <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-elevated rounded-xl text-accent">
                    <User className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-medium text-txt-primary">User Identity</h3>
            </div>
            <div className="space-y-5">
                <div>
                    <label className="block text-[11px] font-bold text-txt-tertiary uppercase tracking-widest mb-3">User Name</label>
                    <input 
                        type="text" 
                        value={localSettings.user_name || ''}
                        onChange={e => handleChange('user_name', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl px-5 py-4 text-txt-primary focus:outline-none focus:border-accent transition-colors"
                        placeholder="How should the AI address you?"
                    />
                </div>
            </div>
        </div>

        {/* Location Section */}
        <div className="p-8 bg-surface border border-border-invisible hover:border-border-subtle rounded-[24px] transition-colors">
            <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-elevated rounded-xl text-accent">
                    <MapPin className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-medium text-txt-primary">Location Services</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label className="block text-[11px] font-bold text-txt-tertiary uppercase tracking-widest mb-3">Latitude</label>
                    <input 
                        type="text" 
                        value={localSettings.lat || ''}
                        onChange={e => handleChange('lat', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl px-5 py-4 text-txt-primary focus:outline-none focus:border-accent transition-colors font-mono"
                    />
                </div>
                <div>
                    <label className="block text-[11px] font-bold text-txt-tertiary uppercase tracking-widest mb-3">Longitude</label>
                    <input 
                        type="text" 
                        value={localSettings.lon || ''}
                        onChange={e => handleChange('lon', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl px-5 py-4 text-txt-primary focus:outline-none focus:border-accent transition-colors font-mono"
                    />
                </div>
                <div className="md:col-span-2">
                    <label className="block text-[11px] font-bold text-txt-tertiary uppercase tracking-widest mb-3">City / Region</label>
                    <input 
                        type="text" 
                        value={localSettings.location_name || ''}
                        onChange={e => handleChange('location_name', e.target.value)}
                        className="w-full bg-input border border-border-subtle rounded-xl px-5 py-4 text-txt-primary focus:outline-none focus:border-accent transition-colors"
                        placeholder="e.g. New York, NY"
                    />
                </div>
            </div>
        </div>

        {/* Voice Section */}
        <div className="p-8 bg-surface border border-border-invisible hover:border-border-subtle rounded-[24px] transition-colors">
            <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-elevated rounded-xl text-accent">
                    <Mic className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-medium text-txt-primary">Voice Settings</h3>
            </div>
            <div>
                <label className="block text-[11px] font-bold text-txt-tertiary uppercase tracking-widest mb-3">TTS Voice (Kokoro)</label>
                <input 
                    type="text" 
                    value={localSettings.tts_voice || 'af_heart'}
                    onChange={e => handleChange('tts_voice', e.target.value)}
                    className="w-full bg-input border border-border-subtle rounded-xl px-5 py-4 text-txt-primary focus:outline-none focus:border-accent transition-colors font-mono"
                    placeholder="af_heart"
                />
                <p className="text-xs text-txt-tertiary mt-2">Options: af_heart, af_bella, am_adam, bf_emma, etc.</p>
            </div>
        </div>

      </div>
    </div>
  );
};

export { SettingsGeneral };