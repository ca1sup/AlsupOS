import React, { useEffect, useRef } from 'react';
import { useAppStore, Message } from '../store/useAppStore';
import ChatBubble from './ChatBubble';

const MessageList: React.FC = () => {
  // FIX: Split selectors to prevent "getSnapshot" infinite loop errors
  const chatHistory = useAppStore((state) => state.chatHistory);
  const isLoading = useAppStore((state) => state.isLoading);
  
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isLoading]);

  return (
    // PB-36 allows for the floating input island
    <div className="h-full overflow-y-auto px-4 md:px-8 pb-36 pt-8 scroll-smooth custom-scrollbar">
      <div className="max-w-[900px] mx-auto">
        
        {/* Empty State: The Liquid Orb */}
        {chatHistory.length === 0 ? (
          <div className="h-[60vh] flex flex-col items-center justify-center text-center animate-fade-in">
             <div className="relative mb-8">
                {/* Orbital Rings */}
                <div className="w-24 h-24 rounded-full bg-accent-dim animate-[pulse_3s_ease-in-out_infinite] flex items-center justify-center">
                   <div className="w-16 h-16 rounded-full bg-accent-glow animate-orb" />
                   <div className="absolute w-8 h-8 rounded-full bg-accent opacity-40 blur-md animate-pulse" />
                </div>
             </div>
             
             <h2 className="text-3xl font-light text-txt-primary mb-3 tracking-tight">
               Welcome Chris
             </h2>
             <p className="text-[15px] text-txt-secondary max-w-xs leading-relaxed">
               I'm ready to think.
             </p>
          </div>
        ) : (
          chatHistory.map((msg: Message, i: number) => (
            <ChatBubble 
                key={i} 
                message={msg} 
                isLast={i === chatHistory.length - 1}
                isLoading={isLoading}
            />
          ))
        )}
        
        <div ref={bottomRef} className="h-4" />
      </div>
    </div>
  );
};

export default MessageList;