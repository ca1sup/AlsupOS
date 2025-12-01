import React, { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { 
  Plus, LayoutDashboard, Settings, FolderOpen, Trash2,
  Stethoscope, FileText, ChevronRight
} from 'lucide-react';
import { cn } from '../lib/utils';
import IngestModal from './IngestModal';
import { useNavigate } from 'react-router-dom';

const Sidebar: React.FC<{ isOpen: boolean; setIsOpen: (o: boolean) => void }> = ({ isOpen, setIsOpen }) => {
  const navigate = useNavigate();
  const { 
    chatSessions, 
    currentSessionId, 
    setCurrentSession,
    deleteSession,
    createSession,
    selectedFolder,
    setSelectedFolder,
    folders,
    fetchFolders,
    fetchSessions
  } = useAppStore();

  const [showIngest, setShowIngest] = useState(false);

  useEffect(() => {
    fetchFolders();
    fetchSessions();
  }, [fetchFolders, fetchSessions]);

  const handleNewChat = async () => {
    await createSession();
    if (window.innerWidth < 768) setIsOpen(false);
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: number) => {
      e.stopPropagation();
      if (confirm('Delete this session?')) {
          await deleteSession(sessionId);
      }
  };

  const handleSessionClick = (id: number) => {
    setCurrentSession(id);
    if (window.innerWidth < 768) setIsOpen(false);
    navigate('/');
  };

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-void/80 backdrop-blur-xl z-40 md:hidden animate-fade-in"
          onClick={() => setIsOpen(false)}
        />
      )}

      <div className={cn(
        "fixed inset-y-0 left-0 z-50 w-72 bg-void border-r border-border-invisible flex flex-col shadow-2xl md:shadow-none transition-transform duration-500 cubic-bezier(0.16, 1, 0.3, 1)",
        isOpen ? "translate-x-0" : "-translate-x-full",
        "md:relative md:translate-x-0"
      )}>
        
        {/* Header */}
        <div className="p-8 pb-6 flex items-center justify-between shrink-0">
           <h1 className="font-light text-2xl text-txt-primary tracking-tight">AlsupOS</h1>
           <button 
            onClick={handleNewChat} 
            className="p-3 bg-surface hover:bg-elevated text-txt-secondary hover:text-txt-primary border border-border-invisible rounded-full transition-all active:scale-90 group"
            title="New Chat"
           >
             <Plus className="w-5 h-5 group-hover:rotate-90 transition-transform" />
           </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-6 space-y-10 py-4">
          
          {/* History */}
          <div className="space-y-3">
             <div className="text-[10px] font-bold text-txt-tertiary uppercase tracking-widest px-1">History</div>
             <div className="space-y-1">
                {chatSessions.map(s => (
                    <div 
                        key={s.id}
                        onClick={() => handleSessionClick(s.id)}
                        className={cn(
                            "group flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer text-sm transition-all active:scale-95",
                            currentSessionId === s.id 
                             ? "bg-surface text-accent font-medium border border-border-subtle" 
                             : "text-txt-secondary hover:text-txt-primary hover:bg-surface/50"
                        )}
                    >
                        <span className="truncate flex-1 font-sans">{s.name}</span>
                        <button 
                            onClick={(e) => handleDeleteSession(e, s.id)}
                            className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/20 hover:text-red-500 rounded-lg transition-all"
                        >
                            <Trash2 className="w-3.5 h-3.5" />
                        </button>
                    </div>
                ))}
             </div>
          </div>

          {/* Knowledge Base */}
          <div className="space-y-3">
             <div className="flex items-center justify-between px-1">
                <span className="text-[10px] font-bold text-txt-tertiary uppercase tracking-widest">Knowledge</span>
                <button 
                  onClick={() => setShowIngest(true)} 
                  className="text-txt-tertiary hover:text-accent transition-colors p-1 hover:bg-surface rounded-lg"
                  title="Add Knowledge"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
             </div>
             <div className="space-y-1">
                <div 
                    onClick={() => setSelectedFolder('all')}
                    className={cn(
                        "flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer text-sm transition-all active:scale-95",
                        selectedFolder === 'all' ? "bg-surface text-accent shadow-sm" : "text-txt-secondary hover:bg-surface/50"
                    )}
                >
                    <FolderOpen className="w-4 h-4 opacity-70" /> 
                    <span className="font-medium">All Files</span>
                    {selectedFolder === 'all' && <ChevronRight className="w-3 h-3 ml-auto opacity-50" />}
                </div>
                {folders.map(f => (
                    <div 
                        key={f}
                        onClick={() => setSelectedFolder(f)}
                        className={cn(
                            "flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer text-sm transition-all active:scale-95",
                            selectedFolder === f ? "bg-surface text-accent shadow-sm" : "text-txt-secondary hover:bg-surface/50"
                        )}
                    >
                        <FileText className="w-4 h-4 opacity-70" /> 
                        <span className="truncate">{f}</span>
                    </div>
                ))}
             </div>
          </div>
        </div>

        {/* Footer Nav */}
        <div className="p-6 border-t border-border-invisible bg-void space-y-2">
           <button 
             onClick={() => { navigate('/clinical'); if(window.innerWidth < 768) setIsOpen(false); }}
             className="w-full flex items-center gap-3 px-4 py-3.5 text-sm font-bold text-accent bg-accent-dim hover:bg-accent/10 rounded-2xl transition-all active:scale-95 border border-accent/20 mb-4"
           >
             <Stethoscope className="w-4 h-4" />
             Clinical Aid
           </button>

           <div className="grid grid-cols-2 gap-2">
              <button 
                onClick={() => navigate('/admin')} 
                className="flex flex-col items-center gap-2 p-3 text-xs font-bold uppercase tracking-wider text-txt-tertiary hover:text-txt-primary hover:bg-surface rounded-xl transition-all active:scale-95"
              >
                <LayoutDashboard className="w-5 h-5" />
                Console
              </button>
              <button 
                onClick={() => navigate('/admin/settings')} 
                className="flex flex-col items-center gap-2 p-3 text-xs font-bold uppercase tracking-wider text-txt-tertiary hover:text-txt-primary hover:bg-surface rounded-xl transition-all active:scale-95"
              >
                <Settings className="w-5 h-5" />
                Settings
              </button>
           </div>
        </div>
      </div>

      <IngestModal isOpen={showIngest} onClose={() => setShowIngest(false)} />
    </>
  );
};

export default Sidebar;