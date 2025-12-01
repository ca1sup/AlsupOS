// src/store/slices/createUISlice.ts
import { StateCreator } from 'zustand';
import { StoreState, UISlice, SourceModalContent } from '../types';

export const createUISlice: StateCreator<StoreState, [], [], UISlice> = (set) => ({
  isSidebarOpen: false,
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  
  // View State
  currentView: 'chat',
  setCurrentView: (view: string) => set({ currentView: view }),
  
  // Focus Mode
  isFocusMode: false,
  toggleFocusMode: (enabled: boolean) => set({ isFocusMode: enabled }),
  
  // TTS
  autoSpeak: false,
  setAutoSpeak: (enabled: boolean) => set({ autoSpeak: enabled }),
  
  // Modals
  isIngestModalOpen: false,
  openIngestModal: () => set({ isIngestModalOpen: true }),
  closeIngestModal: () => set({ isIngestModalOpen: false }),
  
  ingestProgress: { message: '', percent: 0, running: false },
  ingestLog: '',
  
  reSync: async () => {
      // Placeholder for re-sync logic triggered from UI
      set({ ingestProgress: { message: 'Syncing...', percent: 10, running: true } });
      setTimeout(() => set({ ingestProgress: { message: 'Done', percent: 100, running: false } }), 1000);
  },
  
  cancelIngest: () => set({ ingestProgress: { message: 'Cancelled', percent: 0, running: false } }),
  
  // Source Modal
  isSourceModalOpen: false,
  sourceModalContent: { title: '', content: '' },
  openSourceModal: (content: SourceModalContent) => set({ isSourceModalOpen: true, sourceModalContent: content }),
  closeSourceModal: () => set({ isSourceModalOpen: false }),
  
  // Voice Modal
  isVoiceModalOpen: false,
  openVoiceModal: () => set({ isVoiceModalOpen: true }),
  closeVoiceModal: () => set({ isVoiceModalOpen: false }),
});