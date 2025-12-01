import axios from 'axios';
import { 
  ChatSessionSchema, 
  ChatMessageSchema, 
  DashboardDataSchema, 
  PersonaSchema, 
  HealthMetricSchema,
  JournalEntrySchema
} from './schemas';
import { z } from 'zod';

// Export Types derived from Zod Schemas
export type ChatSession = z.infer<typeof ChatSessionSchema> & { isEditing?: boolean; newName?: string };
export type ChatMessage = z.infer<typeof ChatMessageSchema>;
export type DashboardData = z.infer<typeof DashboardDataSchema>;
export type Persona = z.infer<typeof PersonaSchema>;
export type HealthMetric = z.infer<typeof HealthMetricSchema>;
export type JournalEntry = z.infer<typeof JournalEntrySchema>;

export interface HealthStatus { ollama: 'checking'|'online'|'offline'; db: 'checking'|'online'|'offline'; }

const api = axios.create({ baseURL: '/api', timeout: 30000, headers: { 'Content-Type': 'application/json' } });
api.interceptors.response.use(r => r, e => Promise.reject(e));

// --- Core ---
export const fetchHealth = async () => { 
  try { 
    const {data} = await api.get('/health'); 
    return { ollama: data.ollama_status?'online':'offline', db: data.db_status?'online':'offline'}; 
  } catch { 
    return {ollama:'offline',db:'offline'}; 
  } 
};

export const fetchSettings = async () => (await api.get('/settings')).data.settings || {};
export const updateSettings = async (s: any) => api.post('/settings', { settings: s });

// --- Ollama ---
export const fetchOllamaModels = async () => (await api.get('/ollama/models')).data.models || [];
export const pullOllamaModel = async (n: string) => api.post('/ollama/pull', { model_name: n });
export const deleteOllamaModel = async (n: string) => api.delete(`/ollama/model/${encodeURIComponent(n)}`);

// --- Personas ---
export const fetchPersonas = async (): Promise<Persona[]> => {
  const { data } = await api.get('/personas');
  return z.array(PersonaSchema).parse(data.personas);
};
export const savePersona = async (p: Persona) => api.post('/personas', p);
export const deletePersona = async (n: string) => api.delete(`/personas/${n}`);

// --- Files ---
export const fetchFolders = async () => (await api.get('/folders')).data.folders || [];
export const fetchFiles = async (f: string) => (await api.get(`/files/${f}`)).data.files || [];
export const uploadFile = async (f: string, file: File) => { const d=new FormData(); d.append('file', file); return api.post(`/upload/${f}`, d, {headers:{'Content-Type':undefined}}); };
export const uploadAudioAndTranscribe = async (file: File) => { const d=new FormData(); d.append('file', file); return api.post(`/upload_and_transcribe/ingest`, d, {headers:{'Content-Type':undefined}}); };
export const fetchDocumentPreview = async (f: string, n: string) => (await api.get(`/document/preview/${f}/${n}`)).data.content||'';

// --- Chat ---
export const fetchChatSessions = async () => {
  const { data } = await api.get('/chat/sessions');
  const sessions = z.array(ChatSessionSchema).parse(data.sessions);
  return sessions.map(s => ({...s, isEditing: false, newName: s.name}));
};
export const createNewChatSession = async () => {
  const { data } = await api.post('/chat/session');
  const session = ChatSessionSchema.parse(data.session);
  return {...session, isEditing: false, newName: ''};
};
export const fetchChatHistory = async (sid: number) => {
  const { data } = await api.get(`/chat/history/${sid}`);
  return z.array(ChatMessageSchema).parse(data.messages);
};
export const deleteChatSession = async (sid: number) => api.delete(`/chat/session/${sid}`);
export const renameChatSession = async (sid: number, n: string) => api.put(`/chat/session/${sid}`, { name: n });

// --- Dashboard & Jobs ---
export const fetchDashboardData = async () => { 
  const { data } = await api.get('/steward/dashboard'); 
  // We use partial parsing here to be safe, or full parse
  const safeData = DashboardDataSchema.parse({
    ...data,
    journals: data.journals || [],
    memories: [], // Fetched separately
    healthMetrics: [], // Fetched separately
    finance: data.finance || []
  });
  return safeData;
};
export const fetchJournalMemories = async () => {
  const { data } = await api.get('/steward/dashboard/memories');
  return z.array(JournalEntrySchema).parse(data.memories || []);
};
export const fetchHealthMetrics = async () => {
  const { data } = await api.get('/steward/dashboard/health');
  return z.array(HealthMetricSchema).parse(data.health_metrics || []);
};

export const runStewardJob = async () => (await api.post('/steward/run_job')).data.message;
export const runFinanceSync = async () => (await api.post('/steward/run_finance_sync')).data.message;
export const runMedNewsSync = async () => (await api.post('/steward/run_med_news_sync')).data.message;
export const updateTaskStatus = async (tid: number, s: string) => api.post(`/steward/task/${tid}`, { status: s });
export const addTaskFromChat = async (t: string) => (await api.post('/steward/add_task', { task: t })).data;
export const addJournalFromChat = async (c: string) => (await api.post('/steward/add_journal', { content: c })).data;
export const triggerIngest = async (sig: AbortSignal) => { const r=await fetch('/api/ingest', {method:'POST', signal:sig}); if(!r.ok) throw new Error(); return r; };

// --- Backup ---
export const exportBackup = async () => (await api.get('/backup/export', {responseType:'blob'})).data;
export const importBackup = async (file: File) => { const d=new FormData(); d.append('file', file); return api.post('/backup/import', d, {headers:{'Content-Type':undefined}}); };

// --- Memory ---
export const fetchUserFacts = async () => (await api.get('/memory/facts')).data.facts || [];
export const deleteUserFact = async (id: number) => api.delete(`/memory/fact/${id}`);