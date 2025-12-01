import React from 'react';
import { cn } from '../lib/utils';

interface SkeletonLoaderProps {
  className?: string;
  count?: number;
}

const SkeletonLoader: React.FC<SkeletonLoaderProps> = ({ className, count = 1 }) => {
  return (
    <div className="w-full space-y-3 animate-pulse">
      {[...Array(count)].map((_, i) => (
        <div 
            key={i} 
            className={cn(
                "h-4 rounded-lg bg-elevated relative overflow-hidden", 
                className
            )} 
        >
            {/* Liquid Shimmer Effect */}
            <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/5 to-transparent" />
        </div>
      ))}
    </div>
  );
};

export default SkeletonLoader;