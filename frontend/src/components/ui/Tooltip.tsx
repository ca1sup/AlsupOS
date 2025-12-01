import React, { useState } from 'react';
import { HelpCircle } from 'lucide-react';
import { cn } from '../../lib/utils';

interface TooltipProps {
  content: string;
  children?: React.ReactNode;
  className?: string;
}

export const Tooltip: React.FC<TooltipProps> = ({ content, children, className }) => {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <div 
      className={cn("relative inline-flex items-center group", className)}
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      // Support touch interactions
      onClick={() => setIsVisible(!isVisible)} 
    >
      {children || (
        <HelpCircle 
          className="w-4 h-4 text-warm-text-secondary hover:text-pastel-sage transition-colors cursor-help ml-2" 
        />
      )}
      
      {isVisible && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-80 p-3 bg-neutral-900 border border-neutral-800 rounded-lg shadow-2xl z-50 animate-fade-in">
          <div className="text-xs text-gray-300 font-sans leading-relaxed max-h-48 overflow-y-auto custom-scrollbar">
            {content}
          </div>
          {/* Arrow */}
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-neutral-900 border-b border-r border-neutral-800 rotate-45" />
        </div>
      )}
    </div>
  );
};