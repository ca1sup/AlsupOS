export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  // UPDATED: Matches backend/agent.py structure
  sources?: { file: string; page?: number; snippet?: string }[];
  persona?: string;
  timestamp?: string;
}

export interface ChatSession {
  id: number;
  name: string;
  created_at: string;
}

export interface HealthMetric {
  date: string;
  steps_count: number;
  active_calories: number;
  weight_kg: number;
  resting_hr: number;
  sleep_total_duration: string;
}

// --- UPDATED ER TYPES ---
export interface ERPatient {
  id: number;
  room_label: string;      // Fixed: matches ClinicalView
  chief_complaint: string; // Fixed: matches ClinicalView
  age_sex: string;
  acuity_level?: number;
  status: string;
  created_at: string;      // Added
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
  currentChart: ERChart | null; // Fixed type
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

// --- UPDATED SETTINGS SLICE ---
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
  
  fetchDashboard: () => Promise<void>;
  updateTask: (id: number, status: string) => Promise<void>;
}

export type StoreState = ChatSlice & UISlice & SettingsSlice;