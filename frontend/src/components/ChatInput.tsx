import React, { useState, useRef } from 'react';
import { Send, Mic, Paperclip, Square } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import VoiceRecorderModal from './VoiceRecorderModal';
import { cn } from '../lib/utils';

// UPDATED: Personas matching backend
const PERSONAS = ['Steward', 'Vault', 'Clinical', 'Mentor', 'CFO', 'Coach'];

const ChatInput: React.FC = () => {
  const [input, setInput] = useState('');
  const [showRecorder, setShowRecorder] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const { 
    sendMessage, currentSessionId, createSession, 
    selectedFolder, selectedFile, isLoading, stopGeneration,
    activePersona, setPersona, uploadFiles 
  } = useAppStore();

  const handleSend = async () => {
    if (!input.trim()) return;
    
    let sid = currentSessionId;
    if (!sid) {
        sid = await createSession();
    }
    
    if (sid) {
        sendMessage(sid, input, selectedFolder, selectedFile ? selectedFile.name : null);
        setInput('');
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
        }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInput(e.target.value);
      e.target.style.height = 'auto';
      e.target.style.height = `${e.target.scrollHeight}px`;
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
          uploadFiles(e.target.files);
          // Auto-select folder to Inbox to see the new file immediately
          // Or we rely on the file list refreshing automatically via store
      }
  };

  const triggerFileSelect = () => {
      fileInputRef.current?.click();
  };

  return (
    // Container ensures input is clickable
    <div className="p-6 border-t border-white/5 bg-void/80 backdrop-blur-xl transition-all duration-300 pointer-events-auto">
      
      {/* Persona Toggles */}
      <div className="max-w-4xl mx-auto mb-3 flex items-center gap-2 overflow-x-auto no-scrollbar">
        {PERSONAS.map(p => (
            <button
                key={p}
                onClick={() => setPersona(p)}
                className={cn(
                    "px-3 py-1.5 rounded-full text-[11px] font-bold uppercase tracking-wider transition-all border",
                    activePersona === p 
                        ? "bg-accent text-void border-accent shadow-glow" 
                        : "bg-surface text-txt-tertiary border-white/5 hover:text-white hover:bg-white/5"
                )}
            >
                {p}
            </button>
        ))}
      </div>

      {/* Added pointer-events-auto here specifically for the bubble */}
      <div className="max-w-4xl mx-auto flex items-end gap-3 bg-surface p-2 rounded-[20px] border border-white/5 shadow-float focus-within:ring-1 focus-within:ring-accent/50 transition-all pointer-events-auto">
        
        <button 
            className="p-3 text-txt-tertiary hover:text-accent hover:bg-white/5 rounded-xl transition-all active:scale-95"
            onClick={() => setShowRecorder(true)}
            title="Voice Input"
        >
          <Mic size={22} />
        </button>

        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={isLoading ? "Thinking..." : `Ask ${activePersona}...`}
          className="flex-1 max-h-40 min-h-[24px] bg-transparent border-none focus:ring-0 resize-none py-3 text-txt-primary placeholder-txt-tertiary focus:outline-none text-[15px] leading-relaxed custom-scrollbar"
          rows={1}
          disabled={isLoading}
        />

        <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileSelect} 
            className="hidden" 
            multiple 
        />

        <button 
            onClick={triggerFileSelect}
            className="p-3 text-txt-tertiary hover:text-white hover:bg-white/5 rounded-xl transition-all active:scale-95"
            title="Attach File"
        >
            <Paperclip size={22} />
        </button>

        {isLoading ? (
            <button 
                onClick={stopGeneration}
                className="p-3 bg-red-500/20 text-red-400 rounded-xl hover:bg-red-500 hover:text-white transition-all shadow-glow animate-pulse"
                title="Stop Generation"
            >
                <Square size={22} fill="currentColor" />
            </button>
        ) : (
            <button 
                onClick={handleSend}
                disabled={!input.trim()}
                className={`p-3 rounded-xl transition-all shadow-glow active:scale-95 ${
                    input.trim() 
                    ? 'bg-accent text-void hover:bg-white' 
                    : 'bg-white/5 text-txt-tertiary cursor-not-allowed'
                }`}
                title="Send Message"
            >
                <Send size={22} />
            </button>
        )}
      </div>
      
      {showRecorder && (
          <VoiceRecorderModal 
            onClose={() => setShowRecorder(false)} 
            onUpload={async () => { setShowRecorder(false); }}
          />
      )}
    </div>
  );
};

export default ChatInput;