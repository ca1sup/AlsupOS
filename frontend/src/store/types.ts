import { z } from 'zod';

// --- Primitives ---
export const HealthStatusSchema = z.object({
  ollama: z.enum(['checking', 'online', 'offline']),
  db: z.enum(['checking', 'online', 'offline']),
});
export type HealthStatus = z.infer<typeof HealthStatusSchema>;

export const JournalEntrySchema = z.object({
  date: z.string(),
  snippet: z.string(),
});
export type JournalEntry = z.infer<typeof JournalEntrySchema>;

// --- Chat ---
export const SourceSchema = z.object({
  file: z.string(),
  page: z.number().optional(),
  text: z.string(),
});
export type Source = z.infer<typeof SourceSchema>;

export const ChatMessageSchema = z.object({
  role: z.enum(['user', 'assistant', 'system']),
  content: z.string(),
  sources: z.array(SourceSchema).optional(),
  isTyping: z.boolean().optional(),
  isStreaming: z.boolean().optional(),
  persona: z.string().optional(),
  timestamp: z.string().optional(),
});
export type ChatMessage = z.infer<typeof ChatMessageSchema>;

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: { file: string; page?: number; snippet?: string }[];
  persona?: string;
  timestamp?: string;
}

export const ChatSessionSchema = z.object({
  id: z.number(),
  name: z.string(),
  created_at: z.string(),
  last_updated: z.string().optional(),
});
export type ChatSession = z.infer<typeof ChatSessionSchema>;

// --- Dashboard ---
export const HealthMetricSchema = z.object({
  id: z.number().optional(),
  date: z.string(),
  weight_kg: z.number().nullable().optional(),
  active_calories: z.number().nullable().optional(),
  source: z.string().optional(),
  steps_count: z.number().nullable().optional(),
  sleep_total_duration: z.string().nullable().optional(),
  resting_hr: z.number().nullable().optional(),
  hrv_ms: z.number().nullable().optional(),
  vo2_max: z.number().nullable().optional(),
});
export type HealthMetric = z.infer<typeof HealthMetricSchema>;

export const FinanceCategorySchema = z.object({
  category: z.string(),
  budgeted: z.number(),
  spent: z.number(),
  remaining: z.number(),
  percent: z.number(),
});
export type FinanceCategory = z.infer<typeof FinanceCategorySchema>;

export const DashboardDataSchema = z.object({
  suggestions: z.any().nullable(),
  tasks: z.array(z.any()),
  events: z.array(z.any()),
  journals: z.array(JournalEntrySchema).default([]),
  memories: z.array(JournalEntrySchema).default([]),
  healthMetrics: z.array(HealthMetricSchema).default([]),
  finance: z.any().optional(), // Flexible to handle the mock object or real array
});
export type DashboardData = z.infer<typeof DashboardDataSchema>;

// --- Settings & System ---
export const PersonaSchema = z.object({
  name: z.string(),
  icon: z.string(),
  prompt: z.string(),
});
export type Persona = z.infer<typeof PersonaSchema>;

export const OllamaModelSchema = z.object({
  name: z.string(),
  size: z.number(),
  modified_at: z.string(),
});
export type OllamaModel = z.infer<typeof OllamaModelSchema>;

export const FileStatusSchema = z.object({
  name: z.string(),
  status: z.enum(['synced', 'modified', 'pending']),
});
export type FileStatus = z.infer<typeof FileStatusSchema>;

export interface ERPatient {
  id: number;
  room_label: string;
  chief_complaint: string;
  age_sex: string;
  acuity_level?: number;
  status: string;
  created_at: string;
}

export interface ERChart {
  id: number;
  patient_id: number;
  chart_markdown: string;
  clinical_guidance_json?: string;
  differentials?: string;
  clinical_pearls?: string;
  created_at: string;
}

export interface SelectedFile {
  name: string;
  status: string;
}

export interface SourceModalContent {
  title: string;
  content: string;
}

export interface IngestProgress {
  message: string;
  percent: number;
  running: boolean;
}

// --- CHAT SLICE ---
export interface ChatSlice {
  isLoading: boolean;
  chatSessions: ChatSession[];
  currentSessionId: number | null;
  chatHistory: Message[];
  folders: string[];
  folderFiles: any[];
  selectedFolder: string;
  selectedFile: SelectedFile | null; 
  healthStatus: HealthMetric | null;
  erPatients: ERPatient[];
  currentChart: ERChart | null; 
  medicalSources: any[];

  activePersona: string;
  activeWebSocket: WebSocket | null;

  setPersona: (p: string) => void;
  stopGeneration: () => void;
  setCurrentSession: (id: number) => void;
  setChatHistory: (history: Message[]) => void;
  setHealthStatus: (status: HealthMetric) => void;
  setSelectedFolder: (folder: string) => void;
  setSelectedFile: (file: SelectedFile | null) => void;
  fetchFolders: () => Promise<void>;
  fetchFolderFiles: (folder: string) => Promise<void>;
  uploadFiles: (files: FileList | File[]) => Promise<void>;
  uploadVoiceMemo: (blob: Blob, target: string) => Promise<void>;
  ingestFile: (file: File) => Promise<void>;
  ingestUrl: (url: string) => Promise<void>;
  fetchSessions: () => Promise<void>;
  fetchHealth: () => Promise<void>;
  createSession: () => Promise<number | null>;
  deleteSession: (sessionId: number) => Promise<void>;
  fetchHistory: (sid: number) => Promise<void>;
  sendMessage: (sessionId: number, content: string, folder: string, file: string | null) => Promise<void>;
  
  fetchERPatients: () => Promise<void>;
  createERPatient: (room: string, complaint: string, age_sex: string) => Promise<void>;
  deleteERPatient: (pid: number) => Promise<void>;
  fetchERChart: (pid: number) => Promise<void>;
  submitERAudio: (pid: number, blob: Blob) => Promise<void>;
  archivePatient: (pid: number) => Promise<void>;
  fetchMedicalSources: () => Promise<void>;
  addMedicalSource: (name: string, url: string) => Promise<void>;
  deleteMedicalSource: (id: number) => Promise<void>;
}

// --- UI SLICE ---
export interface UISlice {
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  
  currentView: string;
  setCurrentView: (view: string) => void;

  isFocusMode: boolean;
  toggleFocusMode: (enabled: boolean) => void;

  autoSpeak: boolean;
  setAutoSpeak: (enabled: boolean) => void;

  isIngestModalOpen: boolean;
  openIngestModal: () => void;
  closeIngestModal: () => void;
  ingestProgress: IngestProgress;
  ingestLog: string;
  reSync: () => Promise<void>;
  cancelIngest: () => void;

  isSourceModalOpen: boolean;
  sourceModalContent: SourceModalContent;
  openSourceModal: (content: SourceModalContent) => void;
  closeSourceModal: () => void;

  isVoiceModalOpen: boolean;
  openVoiceModal: () => void;
  closeVoiceModal: () => void;
}

// --- SETTINGS SLICE ---
export interface SettingsSlice {
  isInitialized: boolean;
  settings: Record<string, any>;
  availableModels: any[];
  dashboardData: any;

  fetchInitialData: () => Promise<void>;
  updateSettings: (newSettings: Record<string, any>) => Promise<void>;
  loadSettings: (s: Record<string, any>) => void;
  
  runJob: () => Promise<void>;
  runFinanceSync: () => Promise<void>;
  runMedNewsSync: () => Promise<void>;
  
  exportBackup: () => void;
  importBackup: (f: File) => Promise<void>;
  
  fetchModels: () => Promise<void>;
  deleteModel: (name: string) => Promise<void>;
  setActiveModel: (name: string) => Promise<void>;
  pullModel: (repoId: string) => Promise<void>; // <--- ADDED THIS LINE
  
  fetchDashboard: () => Promise<void>;
  updateTask: (id: number, status: string) => Promise<void>;
}

export type StoreState = ChatSlice & UISlice & SettingsSlice;