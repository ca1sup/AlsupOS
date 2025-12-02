import React, { useState, useRef, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { X, Mic, Square, Loader2, Edit3, Check, Play, Pause, ChevronDown } from 'lucide-react';
import { toast } from 'react-toastify';

interface VoiceRecorderModalProps {
  onClose: () => void;
  onUpload: (blob: Blob) => Promise<void>; 
}

const CATEGORIES = [
  { id: 'Inbox', label: 'Inbox' },
  { id: 'Nutrition', label: 'Nutrition' },
  { id: 'Workout', label: 'Workout' },
  { id: 'Journal', label: 'Journal' },
  { id: 'Reminder', label: 'Reminder' },
];

const VoiceRecorderModal: React.FC<VoiceRecorderModalProps> = ({ onClose }) => {
  const [step, setStep] = useState<'record' | 'review'>('record');
  const [category, setCategory] = useState('Inbox');
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [audioURL, setAudioURL] = useState<string | null>(null);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const mimeTypeRef = useRef<string>('');

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (audioURL) URL.revokeObjectURL(audioURL);
    };
  }, [audioURL]);

  const getBestMimeType = () => {
    const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/aac', 'audio/ogg'];
    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) return type;
    }
    return '';
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = getBestMimeType();
      mimeTypeRef.current = mimeType;
      
      mediaRecorderRef.current = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current || 'audio/webm' });
        if (blob.size < 100) {
            toast.warn("Recording too short.");
            return;
        }
        const url = URL.createObjectURL(blob);
        setAudioURL(url);
        await transcribeAudio(blob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      setDuration(0);
      startTimeRef.current = Date.now();
      
      timerRef.current = window.setInterval(() => {
        setDuration(d => d + 1);
      }, 1000);

    } catch (e) {
      console.error("Microphone denied", e);
      toast.error("Microphone access is required.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      if (Date.now() - startTimeRef.current < 1000) {
          toast.info("Hold longer to record.");
          mediaRecorderRef.current.stop();
          setIsRecording(false);
          clearInterval(timerRef.current!);
          return;
      }
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const transcribeAudio = async (blob: Blob) => {
      setIsProcessing(true);
      const formData = new FormData();
      let ext = 'webm';
      if (mimeTypeRef.current.includes('mp4')) ext = 'mp4';
      if (mimeTypeRef.current.includes('aac')) ext = 'aac';
      
      formData.append('file', blob, `voice_memo.${ext}`);
      
      try {
          const res = await fetch('/api/steward/transcribe_temp', { method: 'POST', body: formData });
          if (!res.ok) throw new Error("Error");
          const data = await res.json();
          setTranscript(data.transcript || "");
      } catch (e) {
          toast.error("Transcription failed.");
      } finally {
          setIsProcessing(false);
          setStep('review'); 
      }
  };

  const handleSaveNote = async () => {
      if (!transcript.trim()) {
          toast.warning("Empty note.");
          return;
      }
      setIsProcessing(true);
      try {
          await fetch('/api/steward/save_note', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({ category, content: transcript })
          });
          toast.success(`Saved to ${category}`);
          onClose();
      } catch (e) {
          toast.error("Failed to save.");
      } finally {
          setIsProcessing(false);
      }
  };

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const togglePlayback = () => {
      if (audioRef.current) {
          if (isPlaying) audioRef.current.pause();
          else audioRef.current.play();
          setIsPlaying(!isPlaying);
      }
  };

  return ReactDOM.createPortal(
    <div className="fixed inset-0 z-[9999] flex items-end sm:items-center justify-center bg-black/80 backdrop-blur-sm animate-fade-in">
      
      {/* Container: Bottom sheet on mobile, centered modal on desktop */}
      <div className="bg-surface w-full sm:w-[400px] max-h-[85vh] flex flex-col rounded-t-3xl sm:rounded-2xl shadow-2xl overflow-hidden border-t sm:border border-white/10 animate-slide-up sm:animate-scale-up">
        
        {/* Header */}
        <div className="px-5 py-4 border-b border-white/5 flex items-center justify-between bg-elevated/50 shrink-0">
            <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isRecording ? 'bg-red-500 animate-pulse' : 'bg-accent'}`} />
                <span className="text-sm font-medium text-white">
                    {step === 'record' ? 'Record' : 'Review'}
                </span>
            </div>
            <button onClick={onClose} className="p-1 -mr-2 text-txt-tertiary hover:text-white rounded-full active:bg-white/10">
                <X size={20} />
            </button>
        </div>

        {/* Scrollable Content Area */}
        <div className="p-5 overflow-y-auto flex-1">
            
            {/* Category Dropdown (Space Saver) */}
            <div className="mb-6">
                <label className="block text-[10px] font-bold text-txt-tertiary uppercase tracking-widest mb-1.5">Save To</label>
                <div className="relative">
                    <select 
                        value={category}
                        onChange={(e) => setCategory(e.target.value)}
                        className="w-full bg-elevated border border-white/10 rounded-xl py-3 px-4 text-sm text-white appearance-none focus:outline-none focus:border-accent transition-colors"
                    >
                        {CATEGORIES.map(cat => (
                            <option key={cat.id} value={cat.id}>{cat.label}</option>
                        ))}
                    </select>
                    <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-txt-tertiary">
                        <ChevronDown size={14} />
                    </div>
                </div>
            </div>

            {/* RECORD STEP */}
            {step === 'record' && (
                <div className="flex flex-col items-center justify-center pb-4">
                    <div className={`text-5xl font-mono font-light tracking-tight mb-8 tabular-nums ${isRecording ? 'text-white' : 'text-txt-tertiary'}`}>
                        {formatTime(duration)}
                    </div>
                    
                    {isRecording ? (
                        <button 
                            onClick={stopRecording}
                            className="w-16 h-16 rounded-full bg-white flex items-center justify-center shadow-lg active:scale-95 transition-transform"
                        >
                            <Square size={24} className="text-red-500 fill-current" />
                        </button>
                    ) : (
                        <button 
                            onClick={startRecording}
                            className="w-16 h-16 rounded-full bg-red-500 flex items-center justify-center shadow-[0_0_20px_rgba(239,68,68,0.4)] active:scale-95 transition-transform group"
                        >
                            <Mic size={28} className="text-white" />
                        </button>
                    )}
                    
                    <p className="mt-6 text-[10px] text-txt-tertiary uppercase tracking-widest font-semibold">
                        {isRecording ? "Tap to Stop" : "Tap to Record"}
                    </p>
                </div>
            )}

            {/* REVIEW STEP */}
            {step === 'review' && (
                <div className="space-y-4">
                    {/* Tiny Player */}
                    {audioURL && (
                        <div className="flex items-center gap-3 p-2 bg-elevated rounded-xl border border-white/5">
                            <button onClick={togglePlayback} className="p-2 bg-white text-void rounded-full shrink-0">
                                {isPlaying ? <Pause size={14} fill="currentColor"/> : <Play size={14} fill="currentColor"/>}
                            </button>
                            <div className="h-1 flex-1 bg-white/10 rounded-full overflow-hidden">
                                <div className="h-full bg-accent w-1/2 opacity-50" /> 
                            </div>
                            <span className="text-[10px] font-mono text-txt-secondary shrink-0">{formatTime(duration)}</span>
                            <audio ref={audioRef} src={audioURL} onEnded={() => setIsPlaying(false)} className="hidden" />
                        </div>
                    )}

                    {/* Compact Editor */}
                    <div className="relative">
                        <textarea 
                            value={transcript}
                            onChange={(e) => setTranscript(e.target.value)}
                            className="w-full h-32 bg-elevated border border-white/5 rounded-xl p-3 text-sm leading-relaxed text-txt-primary focus:outline-none focus:border-accent/50 resize-none"
                            placeholder={isProcessing ? "Transcribing..." : "Note content..."}
                        />
                        <div className="absolute bottom-3 right-3 text-txt-tertiary pointer-events-none">
                            <Edit3 size={12} />
                        </div>
                    </div>

                    <div className="flex gap-2 pt-2">
                        <button 
                            onClick={() => { 
                                setStep('record'); 
                                setTranscript(''); 
                                setDuration(0);
                                if(audioURL) URL.revokeObjectURL(audioURL);
                                setAudioURL(null);
                            }}
                            className="flex-1 py-3 rounded-xl bg-white/5 text-txt-secondary text-xs font-bold active:bg-white/10"
                        >
                            Discard
                        </button>
                        <button 
                            onClick={handleSaveNote}
                            disabled={isProcessing}
                            className="flex-[2] py-3 rounded-xl bg-white text-void hover:bg-accent text-xs font-bold flex items-center justify-center gap-2 shadow-lg active:scale-[0.98] transition-transform"
                        >
                            {isProcessing ? <Loader2 className="animate-spin" size={14}/> : <Check size={14} />}
                            Save
                        </button>
                    </div>
                </div>
            )}

            {/* Processing Overlay */}
            {isProcessing && step === 'record' && (
                <div className="absolute inset-0 bg-surface/90 backdrop-blur-sm flex flex-col items-center justify-center z-20">
                    <Loader2 className="w-8 h-8 text-accent animate-spin mb-3" />
                    <p className="text-xs font-medium text-white/80 animate-pulse">Transcribing...</p>
                </div>
            )}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default VoiceRecorderModal;