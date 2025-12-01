import React from 'react';
import { Menu, Plus } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

interface MobileNavProps {
    onMenuClick?: () => void;
}

const MobileNav: React.FC<MobileNavProps> = ({ onMenuClick }) => {
  const toggleSidebar = useAppStore(state => state.toggleSidebar);
  const createSession = useAppStore(state => state.createSession);

  // Default handler if not passed
  const handleMenu = () => {
      if (onMenuClick) onMenuClick();
      else toggleSidebar();
  };

  return (
    <div className="md:hidden fixed top-0 left-0 right-0 h-16 bg-earth-950/80 backdrop-blur-xl border-b border-earth-800/50 flex items-center justify-between px-4 z-30 animate-fade-in glass-panel">
      <button 
        onClick={handleMenu}
        className="p-2.5 -ml-2 text-earth-400 hover:text-earth-200 hover:bg-white/5 rounded-full transition-all active:scale-90"
      >
        <Menu className="w-6 h-6" />
      </button>

      <span className="font-serif italic text-xl text-earth-200 font-bold tracking-wide">AlsupOS</span>

      <button 
        onClick={() => createSession()}
        className="p-2.5 -mr-2 text-flair-sage hover:bg-flair-sage/10 rounded-full transition-all active:scale-90"
      >
        <Plus className="w-6 h-6" />
      </button>
    </div>
  );
};

export default MobileNav;