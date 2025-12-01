import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { X, Upload, Link, FileText, Loader2, CheckCircle } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/useAppStore';

interface IngestModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const IngestModal: React.FC<IngestModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'file' | 'url'>('file');
  const [url, setUrl] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle');
  
  // Note: These actions require the Store updates from Batch 4.5
  const { ingestFile, ingestUrl } = useAppStore();

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    setIsUploading(true);
    setUploadStatus('idle');
    try {
      for (const file of acceptedFiles) {
        await ingestFile(file);
      }
      setUploadStatus('success');
      setTimeout(() => {
          onClose();
          setUploadStatus('idle');
      }, 1500);
    } catch (e) {
      console.error(e);
      setUploadStatus('error');
    } finally {
      setIsUploading(false);
    }
  }, [ingestFile, onClose]);

  // FIX: Cast the entire options object to 'any' to bypass strict prop requirements
  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
      onDrop 
  } as any);

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    setIsUploading(true);
    try {
      await ingestUrl(url);
      setUploadStatus('success');
      setUrl('');
      setTimeout(() => {
        onClose();
        setUploadStatus('idle');
      }, 1500);
    } catch {
      setUploadStatus('error');
    } finally {
      setIsUploading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-6">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-earth-950/80 backdrop-blur-md transition-opacity animate-fade-in" 
        onClick={onClose}
      />

      {/* Glass Panel */}
      <div className="relative w-full max-w-lg bg-earth-900/90 backdrop-blur-xl border border-earth-800 rounded-3xl shadow-2xl transform transition-all animate-slide-up overflow-hidden">
        
        {/* Header */}
        <div className="px-6 py-5 border-b border-earth-800/50 flex items-center justify-between">
          <h2 className="font-serif text-xl text-earth-200 italic">Add Knowledge</h2>
          <button 
            onClick={onClose}
            className="p-2 text-earth-500 hover:text-earth-200 hover:bg-white/5 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs (Segmented Control) */}
        <div className="px-6 pt-6">
            <div className="flex p-1 bg-earth-950/50 rounded-xl border border-earth-800/50">
                <button
                    onClick={() => setActiveTab('file')}
                    className={cn(
                        "flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all duration-300",
                        activeTab === 'file' 
                            ? "bg-earth-800 text-earth-200 shadow-sm" 
                            : "text-earth-500 hover:text-earth-300"
                    )}
                >
                    <Upload className="w-4 h-4" /> Upload Files
                </button>
                <button
                    onClick={() => setActiveTab('url')}
                    className={cn(
                        "flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all duration-300",
                        activeTab === 'url' 
                            ? "bg-earth-800 text-earth-200 shadow-sm" 
                            : "text-earth-500 hover:text-earth-300"
                    )}
                >
                    <Link className="w-4 h-4" /> Add Link
                </button>
            </div>
        </div>

        {/* Content */}
        <div className="p-6 min-h-[200px]">
           {activeTab === 'file' ? (
               <div 
                 {...getRootProps()} 
                 className={cn(
                    "h-48 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-300 group",
                    isDragActive 
                        ? "border-flair-sage bg-flair-sage/10" 
                        : "border-earth-800 hover:border-earth-600 hover:bg-earth-800/30"
                 )}
               >
                  {/* Cast input props to any to avoid ref conflicts */}
                  <input {...(getInputProps() as any)} />
                  <div className="w-12 h-12 rounded-full bg-earth-800 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                      <FileText className="w-6 h-6 text-earth-400 group-hover:text-earth-200" />
                  </div>
                  <p className="text-earth-300 font-medium">Tap to select files</p>
                  <p className="text-earth-500 text-xs mt-1">PDF, TXT, MD supported</p>
               </div>
           ) : (
               <form onSubmit={handleUrlSubmit} className="flex flex-col gap-4 mt-2">
                  <div className="relative group">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                        <Link className="w-5 h-5 text-earth-500 group-focus-within:text-flair-clay transition-colors" />
                    </div>
                    <input 
                        type="url" 
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="https://..."
                        className="w-full pl-12 pr-4 py-4 bg-earth-950/50 border border-earth-800 rounded-xl text-earth-200 placeholder-earth-600 focus:outline-none focus:border-flair-clay focus:ring-1 focus:ring-flair-clay transition-all"
                        autoFocus
                    />
                  </div>
                  <button 
                    type="submit" 
                    disabled={!url || isUploading}
                    className="w-full py-3.5 bg-earth-200 text-earth-950 font-bold rounded-xl hover:bg-white active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Fetch Content
                  </button>
               </form>
           )}

           {/* Status Indicator */}
           {isUploading && (
               <div className="absolute inset-0 bg-earth-950/80 backdrop-blur-sm flex flex-col items-center justify-center rounded-3xl z-10">
                   <Loader2 className="w-10 h-10 text-flair-sage animate-spin mb-3" />
                   <p className="text-earth-200 font-medium animate-pulse">Ingesting knowledge...</p>
               </div>
           )}

           {uploadStatus === 'success' && !isUploading && (
               <div className="absolute inset-0 bg-earth-950/90 backdrop-blur-sm flex flex-col items-center justify-center rounded-3xl z-10 animate-fade-in">
                   <CheckCircle className="w-12 h-12 text-flair-sage mb-3" />
                   <p className="text-earth-200 font-bold text-lg">Added to Brain</p>
               </div>
           )}
        </div>
      </div>
    </div>
  );
};

export default IngestModal;