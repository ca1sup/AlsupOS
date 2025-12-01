
import React, { useEffect, useState } from 'react';
import { Save, Trash2, Plus, Edit2, Bot, Folder } from 'lucide-react';
import { useAppStore } from '../../../store/useAppStore';

const SettingsPersonas: React.FC = () => {
  const [personas, setPersonas] = useState<any[]>([]);
  const [editing, setEditing] = useState<any>(null);
  
  // UPDATED: Grab folders and fetchFolders from store
  const { activePersona, setPersona, folders, fetchFolders } = useAppStore();

  useEffect(() => {
    fetchPersonas();
    // Ensure folders are loaded for the dropdown
    if (folders.length === 0) fetchFolders();
  }, []);

  const fetchPersonas = async () => {
    try {
        const res = await fetch('/api/personas');
        const data = await res.json();
        setPersonas(data.personas || []);
    } catch(e) { console.error(e); }
  };

  const handleSave = async () => {
      if (!editing) return;
      try {
          await fetch('/api/personas', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify(editing)
          });
          setEditing(null);
          fetchPersonas();
      } catch(e) { console.error(e); }
  };

  const handleDelete = async (name: string) => {
      if(!confirm(`Delete persona ${name}?`)) return;
      try {
          await fetch(`/api/personas/${name}`, { method: 'DELETE' });
          fetchPersonas();
      } catch(e) { console.error(e); }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900">AI Personas</h3>
        <button 
            onClick={() => setEditing({ name: 'New Persona', icon: 'Bot', prompt: 'You are...', default_folder: 'all' })}
            className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
            <Plus size={16} /> New
        </button>
      </div>

      {editing && (
          <div className="p-4 bg-gray-50 rounded-lg border border-blue-200 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                  <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">Name</label>
                      <input 
                        value={editing.name}
                        onChange={e => setEditing({...editing, name: e.target.value})}
                        className="w-full p-2 border rounded-md text-sm"
                      />
                  </div>
                  <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">Icon (Lucide Name)</label>
                      <input 
                        value={editing.icon}
                        onChange={e => setEditing({...editing, icon: e.target.value})}
                        className="w-full p-2 border rounded-md text-sm"
                      />
                  </div>
              </div>
              
              {/* NEW: Default Folder Selection */}
              <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Default Folder (RAG Scope)</label>
                  <select 
                    value={editing.default_folder || 'all'}
                    onChange={e => setEditing({...editing, default_folder: e.target.value})}
                    className="w-full p-2 border rounded-md text-sm bg-white"
                  >
                      <option value="all">All Folders (Unrestricted)</option>
                      {folders.map(f => (
                          <option key={f} value={f}>{f}</option>
                      ))}
                  </select>
                  <p className="text-[10px] text-gray-400 mt-1">
                    When active, this persona will default to searching this folder unless overridden.
                  </p>
              </div>

              <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">System Prompt</label>
                  <textarea 
                    value={editing.prompt}
                    onChange={e => setEditing({...editing, prompt: e.target.value})}
                    className="w-full p-2 border rounded-md text-sm font-mono h-32"
                  />
              </div>
              <div className="flex justify-end gap-2">
                  <button onClick={() => setEditing(null)} className="px-3 py-1 text-sm text-gray-500">Cancel</button>
                  <button onClick={handleSave} className="flex items-center gap-1 px-3 py-1 bg-blue-600 text-white rounded text-sm">
                      <Save size={14} /> Save
                  </button>
              </div>
          </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        {personas.map((p) => (
            <div key={p.name} className="flex items-start justify-between p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-300 transition-colors">
                <div className="flex items-start gap-3">
                    <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
                        <Bot size={20} />
                    </div>
                    <div>
                        <h4 className="font-medium text-gray-900 flex items-center gap-2">
                            {p.name}
                            {activePersona === p.name && <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">Active</span>}
                        </h4>
                        
                        {/* Display Default Folder */}
                        <div className="flex items-center gap-1 text-xs text-blue-600 mt-1 mb-1">
                            <Folder size={12} />
                            <span>{p.default_folder || 'All Folders'}</span>
                        </div>
                        
                        <p className="text-xs text-gray-500 line-clamp-2 max-w-md font-mono bg-gray-50 p-1 rounded">
                            {p.prompt}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    <button 
                        onClick={() => setPersona(p.name)}
                        className="p-1.5 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded"
                        title="Set Active"
                    >
                        <div className="w-4 h-4 rounded-full border-2 border-current" />
                    </button>
                    <button 
                        onClick={() => setEditing(p)}
                        className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                    >
                        <Edit2 size={16} />
                    </button>
                    <button 
                        onClick={() => handleDelete(p.name)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                    >
                        <Trash2 size={16} />
                    </button>
                </div>
            </div>
        ))}
      </div>
    </div>
  );
};

export default SettingsPersonas;
