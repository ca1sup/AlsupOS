import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
    User, Bot, FileText, Brain, ChevronDown, ChevronRight,
    Stethoscope, Activity, TrendingUp, Dumbbell, Database, Sparkles 
} from 'lucide-react';
import { Message, useAppStore } from '../store/useAppStore';
import { Tooltip } from './ui/Tooltip';

interface ChatBubbleProps {
  message: Message;
  isLast?: boolean;
  isLoading?: boolean;
}

const ChatBubble: React.FC<ChatBubbleProps> = ({ message, isLast, isLoading }) => {
  const isUser = message.role === 'user';
  
  // FIX: Select only the actions needed to prevent full-store subscription
  const setSelectedFile = useAppStore((state) => state.setSelectedFile);
  const setSelectedFolder = useAppStore((state) => state.setSelectedFolder);
  
  // State for the "Thought Process" dropdown (Finished state)
  const [isThoughtExpanded, setIsThoughtExpanded] = useState(false);

  // --- PARSING LOGIC ---
  const rawContent = message.content || "";
  const thinkStart = rawContent.indexOf('<think>');
  const thinkEnd = rawContent.indexOf('</think>');
  
  // 1. Are we currently thinking? (Start tag exists, no End tag yet, and it's the last message loading)
  const isThinkingActive = thinkStart !== -1 && thinkEnd === -1 && isLast && isLoading;

  // 2. Extract content
  let thoughtContent = '';
  let mainContent = rawContent;
  let activeSnippet = "Thinking...";

  if (thinkStart !== -1) {
    if (thinkEnd !== -1) {
        // Finished Thinking
        thoughtContent = rawContent.substring(thinkStart + 7, thinkEnd).trim();
        mainContent = rawContent.substring(thinkEnd + 8).trim();
    } else {
        // Active Thinking
        thoughtContent = rawContent.substring(thinkStart + 7).trim();
        mainContent = ''; // Hide main content while thinking
        
        // Calculate Snippet (Last non-empty line)
        const lines = thoughtContent.split('\n').filter(line => line.trim().length > 0);
        if (lines.length > 0) {
            activeSnippet = lines[lines.length - 1];
        }
    }
  }

  // Helper to get persona icon
  const getPersonaIcon = (persona: string) => {
      switch (persona) {
          case 'Steward': return <Activity size={16} strokeWidth={2.5} />;
          case 'Clinical': return <Stethoscope size={16} strokeWidth={2.5} />;
          case 'Mentor': return <Brain size={16} strokeWidth={2.5} />;
          case 'CFO': return <TrendingUp size={16} strokeWidth={2.5} />;
          case 'Coach': return <Dumbbell size={16} strokeWidth={2.5} />;
          case 'Vault': return <Database size={16} strokeWidth={2.5} />;
          case 'User': return <User size={16} strokeWidth={2.5} />;
          default: return <Bot size={16} strokeWidth={2.5} />;
      }
  };

  const components = {
    // 1. Handle Citations
    a: ({ href, children, ...props }: any) => {
      if (href && href.startsWith('cite:')) {
        const filename = href.replace('cite:', '');
        return (
          <button
            onClick={() => {
                setSelectedFolder('all'); 
                setSelectedFile({ name: filename, status: 'synced' });
            }}
            className="inline-flex items-center gap-1.5 px-2 py-0.5 mx-1 rounded-md bg-accent/10 text-accent text-xs font-bold hover:bg-accent/20 transition-colors cursor-pointer border border-accent/20"
            title={`Open ${filename}`}
          >
            <FileText size={10} />
            {children}
          </button>
        );
      }
      return (
        <a 
            href={href} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="text-accent underline hover:text-white transition-colors" 
            {...props}
        >
            {children}
        </a>
      );
    },

    // 2. Handle Tables
    table: ({ children }: any) => (
        <div className="overflow-x-auto my-4 border border-white/10 rounded-xl bg-void/30">
            <table className="min-w-full divide-y divide-white/10 text-sm">{children}</table>
        </div>
    ),
    thead: ({ children }: any) => <thead className="bg-white/5">{children}</thead>,
    th: ({ children }: any) => (
        <th className="px-4 py-3 text-left text-xs font-bold text-txt-secondary uppercase tracking-wider">
            {children}
        </th>
    ),
    td: ({ children }: any) => (
        <td className="px-4 py-3 whitespace-nowrap text-txt-primary border-t border-white/5">
            {children}
        </td>
    ),
    
    // 3. Handle Lists
    ul: ({ children }: any) => <ul className="list-disc pl-5 my-2 space-y-1 text-txt-secondary">{children}</ul>,
    ol: ({ children }: any) => <ol className="list-decimal pl-5 my-2 space-y-1 text-txt-secondary">{children}</ol>,
    p: ({ children }: any) => <p className="mb-2 last:mb-0 text-txt-primary leading-relaxed">{children}</p>,
    code: ({ children }: any) => <code className="bg-white/5 px-1.5 py-0.5 rounded text-accent font-mono text-xs">{children}</code>
  };

  const processContent = (text: string) => {
      if (!text) return "";
      const citeRegex = new RegExp("//", "g");
      return text.replace(citeRegex, '[$1](cite:$1)');
  };

  return (
    <div className={`flex w-full mb-8 ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div className={`flex max-w-[85%] md:max-w-[70%] gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        
        {/* Avatar */}
        <div className={`flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center border border-white/5 shadow-glow ${
          isUser ? 'bg-accent text-void' : 'bg-elevated text-accent'
        }`}>
          {isUser ? <User size={16} strokeWidth={2.5} /> : getPersonaIcon(message.persona || "Steward")}
        </div>

        {/* Bubble Content */}
        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} w-full min-w-0`}>
          
          {/* STATE 1: ACTIVE THINKING (Gemini Style) */}
          {!isUser && isThinkingActive && (
             <div className="flex items-center gap-3 px-4 py-3 rounded-2xl bg-surface/50 border border-white/5 shadow-glow backdrop-blur-sm animate-pulse-slow">
                <div className="relative">
                    <Sparkles size={16} className="text-accent animate-pulse" />
                    <div className="absolute inset-0 bg-accent blur-md opacity-20" />
                </div>
                
                <div className="flex items-center gap-2 overflow-hidden">
                    <span className="text-xs font-mono text-accent/80 truncate max-w-[200px] md:max-w-[300px]">
                        {activeSnippet}
                    </span>
                    
                    {/* Bouncing Orbs */}
                    <div className="flex gap-1 items-center pt-1">
                        <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                        <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                        <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce"></span>
                    </div>
                </div>
             </div>
          )}

          {/* STATE 2: STANDARD BUBBLE (Finished Thinking or Normal Message) */}
          {(!isThinkingActive || isUser) && (
            <div className={`px-5 py-4 rounded-2xl shadow-sm text-sm overflow-hidden w-full ${
                isUser 
                ? 'bg-white/5 border border-white/10 text-white rounded-tr-sm' 
                : 'bg-surface border border-white/5 text-txt-primary rounded-tl-sm'
            }`}>
                
                {/* Collapsible Thought Block (Only if thoughts exist and thinking is done) */}
                {!isUser && thoughtContent && (
                    <div className="mb-4 rounded-lg bg-black/20 overflow-hidden border border-white/5">
                        <button 
                            onClick={() => setIsThoughtExpanded(!isThoughtExpanded)}
                            className="w-full flex items-center gap-2 px-3 py-2 text-[11px] font-bold text-txt-tertiary hover:text-accent hover:bg-white/5 transition-colors uppercase tracking-wider group"
                        >
                            <Brain size={12} className="group-hover:text-accent transition-colors" />
                            <span>Thought Process</span>
                            {isThoughtExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        </button>
                        
                        {isThoughtExpanded && (
                            <div className="px-3 py-2.5 text-xs text-txt-secondary font-mono leading-relaxed border-t border-white/5 bg-black/20 whitespace-pre-wrap animate-fade-in">
                                {thoughtContent}
                            </div>
                        )}
                    </div>
                )}

                {/* Main Markdown Content */}
                <div className="markdown-body">
                    <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        components={components}
                    >
                        {processContent(mainContent)}
                    </ReactMarkdown>
                </div>
            </div>
          )}

          {/* Sources Footer with Tooltip Preview */}
          {!isUser && !isThinkingActive && message.sources && message.sources.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2 animate-fade-in">
              {message.sources.map((src, idx) => (
                <Tooltip 
                    key={idx} 
                    content={src.snippet || "No preview available."}
                    className="z-10"
                >
                    <button 
                      onClick={() => {
                          setSelectedFolder('all');
                          setSelectedFile({ name: src.file, status: 'synced' });
                      }}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 bg-elevated hover:bg-white/10 text-txt-tertiary hover:text-white text-[10px] uppercase tracking-wider font-bold rounded-lg transition-all border border-white/5"
                    >
                      <FileText size={10} />
                      <span className="truncate max-w-[120px]">{src.file}</span>
                      {src.page && <span className="opacity-50 ml-1">p.{src.page}</span>}
                    </button>
                </Tooltip>
              ))}
            </div>
          )}
          
          {/* Persona Label */}
          {!isThinkingActive && (
              <span className="text-[10px] font-medium text-txt-tertiary mt-2 px-1 uppercase tracking-widest opacity-50">
                {message.persona || (isUser ? "You" : "Steward")}
              </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatBubble;