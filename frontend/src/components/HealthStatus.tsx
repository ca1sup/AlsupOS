import React, { useEffect } from 'react';
import { useAppStore, StoreState } from '../store/useAppStore';
import { Activity, Heart, Flame, Moon } from 'lucide-react';

const HealthStatus: React.FC = () => {
  // Explicitly typing state fixes the "implicit any" error
  const healthStatus = useAppStore((state: StoreState) => state.healthStatus);
  const fetchHealth = useAppStore((state: StoreState) => state.fetchHealth);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  if (!healthStatus) return null;

  return (
    <div className="flex items-center gap-4 p-3 bg-white/50 backdrop-blur-sm rounded-xl border border-emerald-100 shadow-sm text-xs text-gray-600">
        <div className="flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-emerald-500" />
            <span className="font-medium text-gray-900">{healthStatus.steps_count || 0}</span> steps
        </div>
        <div className="w-px h-3 bg-gray-300" />
        <div className="flex items-center gap-1.5">
            <Flame className="w-3.5 h-3.5 text-orange-500" />
            <span className="font-medium text-gray-900">{healthStatus.active_calories || 0}</span> kcal
        </div>
        <div className="w-px h-3 bg-gray-300 hidden sm:block" />
        <div className="hidden sm:flex items-center gap-1.5">
            <Heart className="w-3.5 h-3.5 text-rose-500" />
            <span className="font-medium text-gray-900">{healthStatus.resting_hr || '--'}</span> bpm
        </div>
        <div className="w-px h-3 bg-gray-300 hidden sm:block" />
         <div className="hidden sm:flex items-center gap-1.5">
            <Moon className="w-3.5 h-3.5 text-indigo-500" />
            <span className="font-medium text-gray-900">{healthStatus.sleep_total_duration || '--'}</span>
        </div>
    </div>
  );
};

export default HealthStatus;