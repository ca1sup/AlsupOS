import React from 'react';
import { UseFormRegisterReturn } from 'react-hook-form';
import { AlertCircle, HelpCircle } from 'lucide-react';
import { cn } from '../../lib/utils';

interface FormInputProps {
  label: string;
  type?: string;
  registration: UseFormRegisterReturn;
  error?: string;
  description?: string;
  placeholder?: string;
  className?: string;
  tooltip?: string;
}

export const FormInput: React.FC<FormInputProps> = ({
  label,
  type = 'text',
  registration,
  error,
  description,
  placeholder,
  className,
  tooltip
}) => {
  return (
    <div className={cn("w-full space-y-2", className)}>
      <div className="flex items-center justify-between">
        <label className="text-[10px] font-bold text-earth-500 uppercase tracking-widest flex items-center gap-2">
          {label}
          {tooltip && (
            <div className="group relative">
              <HelpCircle size={14} className="text-earth-600 cursor-help hover:text-flair-sage transition-colors" />
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-3 bg-earth-900/95 backdrop-blur-xl border border-earth-800 rounded-xl text-xs text-earth-300 leading-relaxed shadow-2xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 font-sans">
                {tooltip}
              </div>
            </div>
          )}
        </label>
      </div>
      
      <div className="relative group">
        <input
          type={type}
          {...registration}
          placeholder={placeholder}
          className={cn(
            // Base: Engraved Cutout Look
            "w-full bg-earth-950 shadow-inner border border-earth-800 rounded-xl px-4 py-3.5 text-sm text-earth-200 placeholder-earth-600/40 font-sans",
            // Focus: Glow & Border (No Ring)
            "focus:outline-none focus:border-flair-sage/80 focus:shadow-[inset_0_2px_4px_rgba(0,0,0,0.5)] transition-all duration-300",
            // Error State
            error && "border-flair-rose/80 focus:border-flair-rose text-flair-rose placeholder-flair-rose/30"
          )}
        />
        {error && (
          <div className="absolute right-3 top-3.5 text-flair-rose animate-pulse">
            <AlertCircle size={18} />
          </div>
        )}
      </div>

      {error ? (
        <p className="text-xs text-flair-rose font-medium animate-slide-up flex items-center gap-1">
            <span className="w-1 h-1 rounded-full bg-flair-rose"/> {error}
        </p>
      ) : description ? (
        <p className="text-xs text-earth-500 font-mono leading-relaxed opacity-80">{description}</p>
      ) : null}
    </div>
  );
};