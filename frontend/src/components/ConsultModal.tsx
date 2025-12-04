import React, { useState, useRef, useEffect } from 'react';
import { X, Send, User, Stethoscope, FileText, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '../lib/utils';
import { Tooltip } from './ui/Tooltip';

interface ConsultModalProps {
  isOpen: boolean;
  onClose: () => void;
  patientId: number | null;
  roomNumber: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: any[];
}

const ConsultModal: React.FC<ConsultModalProps> = ({ isOpen, onClose, patientId, roomNumber }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = () => {
    if (!input.trim() || !patientId) return;

    const userMsg = input;
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setIsLoading(true);

    // Initialize WS if needed
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws/clinical_consult/${patientId}`);
        
        ws.onopen = () => {
            ws.send(userMsg);
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'token') {
                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last.role === 'assistant') {
                        return [...prev.slice(0, -1), { ...last, content: last.content + data.data }];
                    } else {
                        return [...prev, { role: 'assistant', content: data.data }];
                    }
                });
            } else if (data.type === 'sources') {
                setMessages(prev => {
                    const last = prev[prev.length - 1];
                    if (last.role === 'assistant') {
                        return [...prev.slice(0, -1), { ...last, sources: data.data }];
                    }
                    return prev;
                });
            } else if (data.type === 'done') {
                setIsLoading(false);
            }
        };

        ws.onerror = (e) => {
            console.error("Consult WS Error", e);
            setIsLoading(false);
        };

        wsRef.current = ws;
    } else {
        // WS already open
        wsRef.current.send(userMsg);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          handleSendMessage();
      }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      
      <div className="relative w-full max-w-2xl bg-surface border border-white/10 rounded-2xl shadow-2xl flex flex-col h-[80vh] overflow-hidden animate-scale-up">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/5 bg-elevated/50 backdrop-blur-md shrink-0">
            <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-500/20 text-purple-400 rounded-lg">
                    <Stethoscope size={20} />
                </div>
                <div>
                    <h2 className="font-bold text-white text-sm">Attending Consult</h2>
                    <p className="text-xs text-txt-tertiary">Room {roomNumber} • Emergency Medicine DB Access</p>
                </div>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full text-txt-secondary hover:text-white transition-colors">
                <X size={20} />
            </button>
        </div>

        {/* Chat Area - Added overscroll-y-none and touch-pan-y */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar bg-void/50 overscroll-y-none touch-pan-y">
            {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-txt-tertiary opacity-50 gap-3">
                    <Bot size={40} />
                    <p className="text-sm">Ready to consult on this patient.</p>
                </div>
            )}
            
            {messages.map((msg, idx) => (
                <div key={idx} className={cn("flex gap-3", msg.role === 'user' ? "justify-end" : "justify-start")}>
                    {msg.role === 'assistant' && (
                        <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400 shrink-0 mt-1">
                            <Stethoscope size={14} />
                        </div>
                    )}
                    
                    <div className={cn(
                        "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm",
                        msg.role === 'user' 
                            ? "bg-accent text-void rounded-tr-sm" 
                            : "bg-surface border border-white/5 text-txt-primary rounded-tl-sm"
                    )}>
                        <div className="markdown-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                        </div>
                        
                        {/* Sources */}
                        {msg.sources && msg.sources.length > 0 && (
                            <div className="mt-3 flex flex-wrap gap-2 pt-2 border-t border-white/5">
                                {msg.sources.map((src, i) => (
                                    <Tooltip key={i} content={src.snippet}>
                                        <div className="flex items-center gap-1 bg-black/20 hover:bg-black/40 px-2 py-1 rounded text-[10px] text-txt-tertiary border border-white/5 cursor-help transition-colors">
                                            <FileText size={10} />
                                            <span className="truncate max-w-[100px]">{src.file}</span>
                                        </div>
                                    </Tooltip>
                                ))}
                            </div>
                        )}
                    </div>

                    {msg.role === 'user' && (
                        <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-white shrink-0 mt-1">
                            <User size={14} />
                        </div>
                    )}
                </div>
            ))}
            <div ref={scrollRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-white/5 bg-surface shrink-0">
            <div className="relative flex items-end gap-2 bg-black/30 border border-white/10 rounded-xl p-2 focus-within:ring-1 focus-within:ring-purple-500/50 transition-all">
                <textarea 
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about differentials, dosages, or guidelines..."
                    className="flex-1 bg-transparent border-none text-sm text-white placeholder-txt-tertiary focus:ring-0 resize-none max-h-32 py-2 px-2"
                    rows={1}
                    disabled={isLoading}
                />
                <button 
                    onClick={handleSendMessage}
                    disabled={!input.trim() || isLoading}
                    className={cn(
                        "p-2 rounded-lg transition-all",
                        input.trim() && !isLoading
                            ? "bg-purple-500 text-white hover:bg-purple-400 shadow-glow" 
                            : "bg-white/5 text-txt-tertiary cursor-not-allowed"
                    )}
                >
                    <Send size={18} />
                </button>
            </div>
        </div>

      </div>
    </div>
  );
};

export default ConsultModal;