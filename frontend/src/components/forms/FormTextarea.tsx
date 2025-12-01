import React from 'react';
import { UseFormRegisterReturn } from 'react-hook-form';
import { HelpCircle } from 'lucide-react';
import { cn } from '../../lib/utils';

interface FormTextareaProps {
  label: string;
  registration: UseFormRegisterReturn;
  error?: string;
  description?: string;
  placeholder?: string;
  rows?: number;
  className?: string;
  tooltip?: string;
}

export const FormTextarea: React.FC<FormTextareaProps> = ({
  label,
  registration,
  error,
  description,
  placeholder,
  rows = 3,
  className,
  tooltip
}) => {
  return (
    <div className={cn("w-full space-y-2", className)}>
      <label className="text-xs font-bold text-earth-500 uppercase tracking-widest flex items-center gap-2">
        {label}
        {tooltip && (
            <div className="group relative">
              <HelpCircle size={14} className="text-earth-600 cursor-help hover:text-flair-sage transition-colors" />
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 p-3 bg-earth-900 border border-earth-800 rounded-lg text-[10px] text-earth-300 leading-tight shadow-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 normal-case font-sans">
                {tooltip}
              </div>
            </div>
          )}
      </label>
      
      <textarea
        {...registration}
        rows={rows}
        placeholder={placeholder}
        className={cn(
          "w-full bg-earth-950 border border-earth-800 rounded-xl px-4 py-3 text-sm text-earth-200 font-mono placeholder-earth-600/50",
          "focus:outline-none focus:border-flair-sage focus:ring-1 focus:ring-flair-sage/50",
          "transition-all duration-200 resize-y leading-relaxed scrollbar-thin",
          error && "border-flair-rose focus:border-flair-rose"
        )}
      />

      {error ? (
        <p className="text-xs text-flair-rose font-medium">{error}</p>
      ) : description ? (
        <p className="text-xs text-earth-500 font-mono">{description}</p>
      ) : null}
    </div>
  );
};