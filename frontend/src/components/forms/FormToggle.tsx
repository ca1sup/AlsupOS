import React from 'react';
import { Control, Controller } from 'react-hook-form';
import { HelpCircle } from 'lucide-react';
import { cn } from '../../lib/utils';

interface FormToggleProps {
  control: Control<any>;
  name: string;
  label: string;
  description?: string;
  tooltip?: string;
}

export const FormToggle: React.FC<FormToggleProps> = ({ control, name, label, description, tooltip }) => {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field: { onChange, value } }) => (
        <div className="flex items-start justify-between group py-3">
          <div className="flex-1 pr-4">
            <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-bold text-earth-300 group-hover:text-earth-200 transition-colors">{label}</span>
                {tooltip && (
                    <div className="group/tip relative">
                    <HelpCircle size={14} className="text-earth-600 cursor-help hover:text-flair-sage transition-colors" />
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 p-3 bg-earth-900/95 backdrop-blur-xl border border-earth-800 rounded-xl text-xs text-earth-300 leading-relaxed shadow-2xl opacity-0 group-hover/tip:opacity-100 transition-opacity pointer-events-none z-10 font-sans">
                        {tooltip}
                    </div>
                    </div>
                )}
            </div>
            {description && <p className="text-xs text-earth-500 font-mono leading-relaxed">{description}</p>}
          </div>
          
          <button
            type="button"
            role="switch"
            aria-checked={value}
            onClick={() => onChange(!value)}
            className={cn(
              "relative inline-flex h-7 w-12 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-all duration-500 ease-spring focus:outline-none",
              value 
                ? "bg-flair-sage shadow-[0_0_15px_rgba(166,177,140,0.4)]" // Active: Sage Glow
                : "bg-earth-950 border-earth-800 shadow-inner" // Inactive: Engraved Slot
            )}
          >
            <span className="sr-only">Use setting</span>
            <span
              aria-hidden="true"
              className={cn(
                "pointer-events-none inline-block h-6 w-6 transform rounded-full bg-white shadow-lg ring-0 transition duration-500 ease-spring",
                value ? "translate-x-5" : "translate-x-0 opacity-50 bg-earth-500"
              )}
            />
          </button>
        </div>
      )}
    />
  );
};