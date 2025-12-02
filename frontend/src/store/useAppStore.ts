import { create, StateCreator } from 'zustand';
import { createUISlice } from './slices/createUISlice';
import { createSettingsSlice } from './slices/createSettingsSlice';
import { StoreState, ChatSlice, Message, HealthMetric } from './types';

export * from './types';
export const VOICE_MEMO_TARGETS = ['Inbox', 'Journal', 'Worship', 'Homeschool', 'Health'];
export type AppState = StoreState;

// Helper to extract embedded sources from persistent storage string
const parseMessageContent = (msg: Message): Message => {
    if (!msg.content) return msg;
    
    // Look for <sources>[...]</sources> at the end of the string
    const sourceRegex = /<sources>(.*?)<\/sources>$/s;
    const match = msg.content.match(sourceRegex);
    
    if (match && match[1]) {
        try {
            const sources = JSON.parse(match[1]);
            // Remove the XML tag from the visible content
            const cleanContent = msg.content.replace(sourceRegex, '').trim();
            return { ...msg, content: cleanContent, sources };
        } catch (e) {
            console.error("Failed to parse sources JSON", e);
            return msg;
        }
    }
    return msg;
};

const createChatSlice: StateCreator<StoreState, [], [], ChatSlice> = (set, get) => ({
  isLoading: false,
  chatSessions: [],
  currentSessionId: null,
  chatHistory: [],
  folders: [],
  folderFiles: [],
  selectedFolder: 'all',
  selectedFile: null,
  healthStatus: null,
  erPatients: [],
  currentChart: null,
  medicalSources: [],
  
  // --- Persona State ---
  activePersona: 'Steward', 
  setPersona: (p) => set({ activePersona: p }),

  // --- WebSocket Control ---
  activeWebSocket: null,

  stopGeneration: () => {
      const ws = get().activeWebSocket;
      if (ws) {
          ws.close();
          console.log("Generation stopped by user.");
      }
      set({ isLoading: false, activeWebSocket: null });
  },

  setCurrentSession: (id) => {
    set({ currentSessionId: id });
    get().fetchHistory(id);
  },
  setChatHistory: (history) => set({ chatHistory: history }),
  setHealthStatus: (status) => set({ healthStatus: status }),

  setSelectedFolder: (folder) => {
      set({ selectedFolder: folder, selectedFile: null });
      if (folder !== 'all') {
          get().fetchFolderFiles(folder);
      } else {
          set({ folderFiles: [] });
      }
  },
  setSelectedFile: (file) => set({ selectedFile: file }),

  fetchFolders: async () => {
    try {
        const res = await fetch('/api/folders');
        const data = await res.json();
        set({ folders: data.folders || [] });
    } catch (e) { console.error(e); }
  },

  fetchFolderFiles: async (folder: string) => {
    try {
        const res = await fetch(`/api/files/${encodeURIComponent(folder)}`);
        const data = await res.json();
        set({ folderFiles: data.files || [] });
    } catch (e) { 
        console.error(e); 
        set({ folderFiles: [] });
    }
  },
  
  uploadFiles: async (files) => {
    // 1. Auto-open modal to show progress
    set({ isIngestModalOpen: true });

    const formData = new FormData();
    if (files instanceof FileList) {
        Array.from(files).forEach(f => formData.append('files', f));
    } else {
        files.forEach(f => formData.append('files', f));
    }
    
    // Default to 'Inbox' if selected folder is 'all', otherwise use selected
    const targetFolder = get().selectedFolder === 'all' ? 'Inbox' : get().selectedFolder;
    
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `/api/upload/${encodeURIComponent(targetFolder)}`);

        // Track Progress
        xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                set({ 
                    ingestProgress: { 
                        message: `Uploading to ${targetFolder}...`, 
                        percent: percent, 
                        running: true 
                    } 
                });
            }
        };

        xhr.onload = async () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                set({ 
                    ingestProgress: { 
                        message: 'Processing...', 
                        percent: 100, 
                        running: true 
                    } 
                });
                
                // Refresh data
                await get().fetchFolders();
                if (get().selectedFolder !== 'all') {
                    await get().fetchFolderFiles(get().selectedFolder);
                }
                
                // Complete
                set({ 
                    ingestProgress: { 
                        message: 'Done', 
                        percent: 100, 
                        running: false 
                    } 
                });
                resolve();
            } else {
                console.error("Upload failed", xhr.responseText);
                set({ 
                    ingestProgress: { 
                        message: 'Error uploading', 
                        percent: 0, 
                        running: false 
                    } 
                });
                reject(new Error(xhr.statusText));
            }
        };

        xhr.onerror = () => {
            console.error("Network error during upload");
            set({ 
                ingestProgress: { 
                    message: 'Network Error', 
                    percent: 0, 
                    running: false 
                } 
            });
            reject(new Error("Network Error"));
        };

        xhr.send(formData);
    });
  },

  uploadVoiceMemo: async (blob, target) => {
      const formData = new FormData();
      formData.append('file', blob, 'memo.webm');
      formData.append('target', target);
      try {
          await fetch('/api/upload/voice', { method: 'POST', body: formData });
      } catch (e) { console.error(e); }
  },

  ingestFile: async (file: File) => {
      await get().uploadFiles([file]);
  },

  ingestUrl: async (url: string) => {
      try {
          set({ ingestProgress: { message: 'Fetching URL...', percent: 50, running: true } });
          const res = await fetch('/api/ingest/url', { 
              method: 'POST', 
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ url }) 
          });
          if (!res.ok) throw new Error("Failed to ingest URL");
          await get().fetchFolders();
          set({ ingestProgress: { message: 'Done', percent: 100, running: false } });
      } catch (e) { 
          console.error(e);
          set({ ingestProgress: { message: 'Error', percent: 0, running: false } }); 
          throw e;
      }
  },

  fetchSessions: async () => {
    try {
        const res = await fetch('/api/chat/sessions');
        const data = await res.json();
        set({ chatSessions: data.sessions || [] });
    } catch (e) { console.error(e); }
  },

  fetchHealth: async () => {
    try {
        const res = await fetch('/api/steward/dashboard/health');
        const data = await res.json();
        if (data.health_metrics && data.health_metrics.length > 0) {
            set({ healthStatus: data.health_metrics[0] as HealthMetric });
        }
    } catch (e) { console.error(e); }
  },

  createSession: async () => {
    try {
        const res = await fetch('/api/chat/session', { method: 'POST' });
        const data = await res.json();
        set((state: StoreState) => ({ 
            chatSessions: [data.session, ...state.chatSessions],
            currentSessionId: data.session.id,
            chatHistory: []
        }));
        return data.session.id;
    } catch (e) { console.error(e); return null; }
  },

  deleteSession: async (sessionId: number) => {
      try {
          await fetch(`/api/chat/session/${sessionId}`, { method: 'DELETE' });
          set((state: StoreState) => {
              const newSessions = state.chatSessions.filter(s => s.id !== sessionId);
              const newCurrentId = state.currentSessionId === sessionId 
                  ? (newSessions.length > 0 ? newSessions[0].id : null) 
                  : state.currentSessionId;
              
              if (state.currentSessionId === sessionId && newCurrentId) {
                  get().fetchHistory(newCurrentId);
              }

              return { 
                  chatSessions: newSessions,
                  currentSessionId: newCurrentId,
                  chatHistory: state.currentSessionId === sessionId && !newCurrentId ? [] : state.chatHistory
              };
          });
      } catch (e) { console.error("Failed to delete session", e); }
  },

  fetchHistory: async (sid) => {
      set({ isLoading: true });
      try {
          const res = await fetch(`/api/chat/history/${sid}`);
          const data = await res.json();
          // Apply parsing to extract sources from content
          const parsedMessages = (data.messages || []).map(parseMessageContent);
          set({ chatHistory: parsedMessages });
      } catch (e) { console.error(e); } 
      finally { set({ isLoading: false }); }
  },

  sendMessage: async (sessionId, content, folder, file) => {
    // Stop any existing generation
    get().stopGeneration();

    set({ isLoading: true });
    
    const currentPersona = get().activePersona;
    
    const userMsg: Message = { role: 'user', content, persona: 'User' };
    const botMsg: Message = { role: 'assistant', content: '', persona: currentPersona };
    
    set((state: StoreState) => ({ 
        chatHistory: [...state.chatHistory, userMsg, botMsg] 
    }));

    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
        
        // Store Ref
        set({ activeWebSocket: ws });

        ws.onopen = () => {
            ws.send(JSON.stringify({
                session_id: sessionId,
                query: content,
                folder: folder,
                file: file,
                persona: currentPersona 
            }));
        };

        let fullResponse = "";
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'token') {
                fullResponse += data.data;
                set((state: StoreState) => {
                    const newHistory = [...state.chatHistory];
                    if (newHistory.length > 0) {
                        const lastIdx = newHistory.length - 1;
                        if (newHistory[lastIdx].role === 'assistant') {
                            newHistory[lastIdx] = { ...newHistory[lastIdx], content: fullResponse };
                        }
                    }
                    return { chatHistory: newHistory };
                });
            } else if (data.type === 'sources') {
                // NEW: Handle incoming source data
                set((state: StoreState) => {
                    const newHistory = [...state.chatHistory];
                    if (newHistory.length > 0) {
                        const lastIdx = newHistory.length - 1;
                        if (newHistory[lastIdx].role === 'assistant') {
                            newHistory[lastIdx] = { 
                                ...newHistory[lastIdx], 
                                sources: data.data // Attach structured sources
                            };
                        }
                    }
                    return { chatHistory: newHistory };
                });
            } else if (data.type === 'done') {
                ws.close();
                set({ isLoading: false, activeWebSocket: null });
            }
        };
        
        ws.onerror = (e) => { 
            console.error("WS Error", e); 
            set({ isLoading: false, activeWebSocket: null }); 
        };
        
    } catch (e) { 
        console.error(e); 
        set({ isLoading: false, activeWebSocket: null }); 
    }
  },

  // === ER ACTIONS ===
  fetchERPatients: async () => {
      try {
          const res = await fetch('/api/er/dashboard');
          const data = await res.json();
          set({ erPatients: data.patients || [] });
      } catch (e) { console.error(e); }
  },

  createERPatient: async (room, complaint, age_sex) => {
      try {
        await fetch('/api/er/patient', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ room, complaint, age_sex })
        });
        get().fetchERPatients();
      } catch(e) { console.error(e); }
  },

  deleteERPatient: async (pid: number) => {
      try {
          await fetch(`/api/er/patient/${pid}`, { method: 'DELETE' });
          get().fetchERPatients();
          // Clear current chart if it matches the deleted ID
          const current = get().currentChart;
          if (current && current.patient_id === pid) {
              set({ currentChart: null });
          }
      } catch(e) { console.error(e); }
  },

  fetchERChart: async (pid: number) => {
      try {
          const res = await fetch(`/api/er/chart/${pid}`);
          const data = await res.json();
          set({ currentChart: data.chart });
      } catch (e) { console.error(e); }
  },

  submitERAudio: async (pid, blob) => {
      const formData = new FormData();
      formData.append('file', blob, 'er_dictation.webm');
      try {
          await fetch(`/api/er/update_audio/${pid}`, { method: 'POST', body: formData });
      } catch(e) { console.error(e); }
  },

  archivePatient: async (pid) => {
      try {
          await fetch(`/api/er/archive/${pid}`, { method: 'POST' });
          get().fetchERPatients();
      } catch(e) { console.error(e); }
  },

  fetchMedicalSources: async () => {
      try {
          const res = await fetch('/api/er/sources');
          const data = await res.json();
          set({ medicalSources: data.sources || [] });
      } catch(e) { console.error(e); }
  },

  addMedicalSource: async (name, url) => {
      try {
          await fetch('/api/er/sources', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({ name, url })
          });
          get().fetchMedicalSources();
      } catch(e) { console.error(e); }
  },

  deleteMedicalSource: async (id) => {
      try {
          await fetch(`/api/er/sources/${id}`, { method: 'DELETE' });
          get().fetchMedicalSources();
      } catch(e) { console.error(e); }
  }
});

export const useAppStore = create<StoreState>()((...a) => ({
  ...createChatSlice(...a),
  ...createUISlice(...a),
  ...createSettingsSlice(...a),
}));