// src/store/slices/createSettingsSlice.ts
import { StateCreator } from 'zustand';
import { StoreState, SettingsSlice, HealthMetric } from '../types';

// Extended API helper
const api = {
    getSettings: async () => (await fetch('/api/settings')).json(),
    updateSettings: async (s: any) => fetch('/api/settings', { method: 'POST', body: JSON.stringify({settings: s}), headers: {'Content-Type':'application/json'} }),
    
    // Jobs
    runJob: () => fetch('/api/steward/run_job', { method: 'POST' }),
    runFinance: () => fetch('/api/steward/run_finance_sync', { method: 'POST' }),
    runMed: () => fetch('/api/steward/run_med_news_sync', { method: 'POST' }),
    
    // Model Management
    fetchModels: async () => (await fetch('/api/models')).json(),
    deleteModel: (id: string) => fetch(`/api/models/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    pullModel: (repo_id: string) => fetch('/api/models/pull', { 
        method: 'POST', 
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ repo_id }) 
    }),

    // Data
    importBackup: (f: File) => { const d = new FormData(); d.append('file', f); return fetch('/api/backup/import', { method: 'POST', body: d }); },
    updateTask: (id: number, s: string) => fetch(`/api/steward/task/${id}`, { method: 'POST', body: JSON.stringify({status: s}), headers: {'Content-Type':'application/json'} }),
    fetchDashboard: async () => (await fetch('/api/steward/dashboard')).json(),
};

export const createSettingsSlice: StateCreator<StoreState, [], [], SettingsSlice> = (set, get) => ({
    isInitialized: false,
    settings: {},
    availableModels: [],
    dashboardData: null,

    fetchInitialData: async () => {
        if (get().isInitialized) return;
        try {
            const [sRes, mRes, hRes] = await Promise.all([
                api.getSettings(),
                api.fetchModels(),
                fetch('/api/steward/dashboard/health').then(r => r.json())
            ]);
            
            set({
                settings: sRes.settings || {},
                availableModels: mRes.models || [],
                healthStatus: (hRes.health_metrics && hRes.health_metrics[0]) ? (hRes.health_metrics[0] as HealthMetric) : null,
                isInitialized: true
            });

            // Load Chat Sessions too
            get().fetchSessions();

        } catch (e) { console.error("Init failed", e); }
    },

    updateSettings: async (s: Record<string, any>) => { 
        await api.updateSettings(s); 
        set({ settings: s }); 
    },
    
    loadSettings: (s: Record<string, any>) => set({ settings: s }),

    runJob: async () => { await api.runJob(); },
    runFinanceSync: async () => { await api.runFinance(); },
    runMedNewsSync: async () => { await api.runMed(); },

    exportBackup: () => { window.open('/api/backup/export', '_blank'); },
    importBackup: async (f: File) => { await api.importBackup(f); window.location.reload(); },

    fetchModels: async () => {
        const data = await api.fetchModels();
        set({ availableModels: data.models || [] });
    },

    deleteModel: async (n: string) => {
        await api.deleteModel(n);
        // Delay fetch slightly to allow file system to catch up
        setTimeout(() => get().fetchModels(), 1000);
    },

    setActiveModel: async (n: string) => {
        const s = { ...get().settings, llm_model: n };
        await get().updateSettings(s);
    },
    
    pullModel: async (repoId: string) => {
        await api.pullModel(repoId);
    },

    fetchDashboard: async () => {
        try {
            const data = await api.fetchDashboard();
            set({ dashboardData: data });
        } catch (e) { console.error(e); }
    },

    updateTask: async (id: number, status: string) => {
         await api.updateTask(id, status);
         get().fetchDashboard(); // Refresh after update
    }
});