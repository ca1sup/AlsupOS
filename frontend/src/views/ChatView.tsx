import React, { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import Sidebar from '../components/Sidebar';
import MessageList from '../components/MessageList';
import ChatInput from '../components/ChatInput';
import IngestModal from '../components/IngestModal';
import { Menu } from 'lucide-react';
import VoiceRecorderModal from '../components/VoiceRecorderModal';
import { cn } from '../lib/utils';
import { toast } from 'react-toastify';

const ChatView: React.FC = () => {
  const { 
    isSidebarOpen, 
    toggleSidebar, 
    chatSessions, 
    currentSessionId,
    isIngestModalOpen, 
    closeIngestModal,
    // Add these from the store
    isVoiceModalOpen,
    closeVoiceModal
  } = useAppStore();

  const [status, setStatus] = useState({ ollama: 'checking', db: 'checking' });

  // Health Check Loop
  useEffect(() => {
    const check = async () => {
        try {
            const res = await fetch('/api/health');
            const data = await res.json();
            setStatus({ ollama: data.ollama_status ? 'online' : 'offline', db: data.db_status ? 'online' : 'offline' });
        } catch {
            setStatus({ ollama: 'offline', db: 'offline' });
        }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  // Handle Voice Upload
  const handleVoiceUpload = async (blob: Blob) => {
    const formData = new FormData();
    formData.append('file', blob, 'voice_memo.webm');
    
    try {
      // Assuming you have an endpoint for this, or use the ingest endpoint
      const res = await fetch('/api/ingest/voice', {
        method: 'POST',
        body: formData,
      });
      
      if (!res.ok) throw new Error('Upload failed');
      
      toast.success('Voice memo uploaded successfully');
      closeVoiceModal();
    } catch (error) {
      console.error('Voice upload error:', error);
      toast.error('Failed to upload voice memo');
    }
  };

  const currentChatName = chatSessions.find((s: any) => s.id === currentSessionId)?.name || 'New Session';

  return (
    <div className="flex h-[100dvh] bg-void overflow-hidden selection:bg-accent/20 selection:text-accent-bright">
      
      {/* Navigation */}
      <Sidebar isOpen={isSidebarOpen} setIsOpen={toggleSidebar} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full relative min-w-0 transition-all duration-500 ease-spring">
        
        {/* GLASS HEADER */}
        <header className="absolute top-0 left-0 right-0 h-20 pt-safe-top px-8 flex items-center justify-between z-20 glass-panel transition-all">
          
          <div className="flex items-center gap-6">
             {/* Mobile Menu Trigger */}
             <button 
               onClick={toggleSidebar} 
               className="md:hidden p-2 -ml-2 text-txt-secondary hover:text-txt-primary hover:bg-white/5 rounded-full transition-all active:scale-90"
             >
               <Menu className="w-6 h-6" />
             </button>
             
             {/* Clean Title */}
             <h1 className="font-sans font-light text-2xl text-txt-primary tracking-tight truncate max-w-[200px] md:max-w-md opacity-90">
               {currentChatName}
             </h1>
          </div>
          
          {/* Status Dots */}
          <div className="flex items-center gap-3">
             <div className="flex gap-2 bg-surface/50 p-2.5 rounded-full border border-border-subtle/50 backdrop-blur-md">
                <div 
                    title={`Database: ${status.db}`}
                    className={cn(
                        "w-2 h-2 rounded-full transition-all duration-500", 
                        status.db === 'online' ? "bg-accent shadow-[0_0_8px_rgba(255,138,101,0.6)]" : "bg-red-500 opacity-50"
                    )} 
                />
                <div 
                    title={`AI Engine: ${status.ollama}`}
                    className={cn(
                        "w-2 h-2 rounded-full transition-all duration-500", 
                        status.ollama === 'online' ? "bg-accent shadow-[0_0_8px_rgba(255,138,101,0.6)]" : "bg-red-500 opacity-50"
                    )} 
                />
             </div>
          </div>
        </header>

        {/* MESSAGES CANVAS */}
        <div className="flex-1 min-h-0 relative flex flex-col w-full pt-20">
            <MessageList />
        </div>

        {/* INPUT ISLAND - REMOVED pointer-events-none */}
        <div className="absolute bottom-0 left-0 right-0 z-30">
           <ChatInput />
        </div>

        {/* Modals */}
        <IngestModal isOpen={isIngestModalOpen} onClose={closeIngestModal} />
        
        {/* Fixed: Conditional render and props passed */}
        {isVoiceModalOpen && (
            <VoiceRecorderModal 
                onClose={closeVoiceModal}
                onUpload={handleVoiceUpload}
            />
        )}
      </div>
    </div>
  );
};

export default ChatView;