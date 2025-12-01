import React, { useState } from 'react';
import { Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import Dashboard from '../components/admin/Dashboard';
import { SettingsGeneral } from '../components/admin/settings/SettingsGeneral';
import { SettingsAI } from '../components/admin/settings/SettingsAI';
import { SettingsIntegrations } from '../components/admin/settings/SettingsIntegrations';
import { SettingsMemory } from '../components/admin/settings/SettingsMemory';
import { SettingsModules } from '../components/admin/settings/SettingsModules';
import SettingsModels from '../components/admin/settings/SettingsModels';

import { 
  LayoutDashboard, Settings, HardDrive, 
  ChevronLeft, Cpu, Globe, Database, LayoutGrid, Menu
} from 'lucide-react';
import { cn } from '../lib/utils';

const AdminView: React.FC = () => {
  const location = useLocation();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const navItems = [
    { path: '/admin', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/admin/settings', icon: Settings, label: 'General' },
    { path: '/admin/settings/ai', icon: Cpu, label: 'Brain & Prompts' },
    { path: '/admin/settings/models', icon: HardDrive, label: 'LLM Models' },
    { path: '/admin/settings/integrations', icon: Globe, label: 'Integrations' },
    { path: '/admin/settings/memory', icon: Database, label: 'Memory' },
    { path: '/admin/settings/modules', icon: LayoutGrid, label: 'Modules' },
  ];

  return (
    <div className="min-h-screen bg-void flex flex-col md:flex-row text-txt-primary font-sans selection:bg-accent/20">
      
      {/* Mobile Header */}
      <div className="md:hidden p-4 border-b border-border-invisible bg-void/80 backdrop-blur-xl flex items-center justify-between sticky top-0 z-40">
        <button 
          onClick={() => setIsSidebarOpen(true)}
          className="p-2 -ml-2 hover:bg-surface rounded-lg text-txt-secondary hover:text-txt-primary transition-colors"
        >
          <Menu className="w-6 h-6" />
        </button>
        <span className="font-medium tracking-tight text-txt-primary">Control Panel</span>
        <div className="w-6" />
      </div>

      {/* Mobile Overlay */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 bg-void/90 backdrop-blur-sm z-40 md:hidden animate-fade-in"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Admin Sidebar */}
      <aside className={cn(
        "fixed inset-y-0 left-0 z-50 w-72 bg-void border-r border-border-invisible flex flex-col transition-transform duration-500 cubic-bezier(0.16, 1, 0.3, 1) md:relative md:translate-x-0",
        isSidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="p-8 border-b border-border-invisible">
           <Link to="/" className="flex items-center gap-2 text-[11px] font-bold text-txt-tertiary hover:text-accent transition-colors mb-6 uppercase tracking-widest group">
             <ChevronLeft className="w-3 h-3 group-hover:-translate-x-1 transition-transform" />
             Return to App
           </Link>
           <h1 className="text-2xl font-light text-txt-primary tracking-tight">Control Panel</h1>
        </div>
        
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto custom-scrollbar">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setIsSidebarOpen(false)}
                className={cn(
                  "flex items-center gap-3 px-4 py-3.5 text-sm font-medium rounded-xl transition-all duration-300",
                  isActive 
                    ? "bg-surface text-accent shadow-[0_0_20px_rgba(0,0,0,0.2)]" 
                    : "text-txt-secondary hover:text-txt-primary hover:bg-surface/50"
                )}
              >
                <item.icon className={cn("w-4 h-4 transition-colors", isActive ? "text-accent" : "text-txt-tertiary group-hover:text-txt-secondary")} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto bg-void h-[calc(100vh-65px)] md:h-screen custom-scrollbar">
         <div className="max-w-7xl mx-auto p-6 md:p-12 pb-32">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/settings" element={<SettingsGeneral />} />
              <Route path="/settings/ai" element={<SettingsAI />} />
              <Route path="/settings/integrations" element={<SettingsIntegrations />} />
              <Route path="/settings/models" element={<SettingsModels />} />
              <Route path="/settings/memory" element={<SettingsMemory />} />
              <Route path="/settings/modules" element={<SettingsModules />} />
              <Route path="*" element={<Navigate to="/admin" />} />
            </Routes>
         </div>
      </main>
    </div>
  );
};

export default AdminView;