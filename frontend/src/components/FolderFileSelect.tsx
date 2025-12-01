import React, { useEffect, useState } from 'react';
import { FileText, Folder, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';

// Define type locally since it's missing from the store export
export type FileStatus = 'synced' | 'modified' | 'pending';

interface FileItem {
  name: string;
  status: FileStatus;
}

interface FolderFileSelectProps {
  folder: string;
  selectedFile: string | null;
  onSelect: (filename: string) => void;
}

const FolderFileSelect: React.FC<FolderFileSelectProps> = ({ folder, selectedFile, onSelect }) => {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchFiles = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/files/${folder}`);
        if (!res.ok) throw new Error('Failed to fetch files');
        const data = await res.json();
        setFiles(data.files || []);
      } catch (err: any) {
        console.error(err);
        setError('Unable to load files.');
      } finally {
        setLoading(false);
      }
    };

    if (folder) {
      fetchFiles();
    }
  }, [folder]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-gray-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        <span className="text-sm">Loading files...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center p-8 text-red-400">
        <AlertCircle className="w-5 h-5 mr-2" />
        <span className="text-sm">{error}</span>
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-gray-400 border-2 border-dashed border-gray-200 rounded-xl">
        <Folder className="w-8 h-8 mb-2 opacity-50" />
        <span className="text-sm">No files in this folder.</span>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {files.map((file) => {
        const isSelected = selectedFile === file.name;
        const statusColor = {
          synced: 'text-emerald-500',
          modified: 'text-amber-500',
          pending: 'text-blue-500 animate-pulse',
        }[file.status] || 'text-gray-400';

        const Icon = file.status === 'synced' ? CheckCircle : FileText;

        return (
          <button
            key={file.name}
            onClick={() => onSelect(file.name)}
            className={cn(
              "relative flex items-center p-3 text-left transition-all duration-200 border rounded-xl hover:shadow-md",
              isSelected 
                ? "bg-indigo-50 border-indigo-200 ring-1 ring-indigo-200" 
                : "bg-white border-gray-200 hover:border-gray-300"
            )}
          >
            <div className={cn("p-2 rounded-lg mr-3", isSelected ? "bg-indigo-100" : "bg-gray-50")}>
              <Icon className={cn("w-5 h-5", statusColor)} />
            </div>
            <div className="flex-1 min-w-0">
              <p className={cn("text-sm font-medium truncate", isSelected ? "text-indigo-900" : "text-gray-700")}>
                {file.name}
              </p>
              <p className="text-xs text-gray-500 capitalize">
                {file.status}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
};

export default FolderFileSelect;