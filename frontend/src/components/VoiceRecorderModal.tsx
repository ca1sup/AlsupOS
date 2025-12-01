import React, { useState, useRef, useEffect } from 'react';
import { X, Mic, Square, Save, Loader2 } from 'lucide-react';

interface VoiceRecorderModalProps {
  onClose: () => void;
  onUpload: (blob: Blob) => Promise<void>;
}

const VoiceRecorderModal: React.FC<VoiceRecorderModalProps> = ({ onClose, onUpload }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [audioURL, setAudioURL] = useState<string | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [duration, setDuration] = useState(0);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (audioURL) URL.revokeObjectURL(audioURL);
    };
  }, [audioURL]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        setAudioURL(URL.createObjectURL(blob));
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setDuration(0);
      
      timerRef.current = window.setInterval(() => {
        setDuration(d => d + 1);
      }, 1000);

    } catch (e) {
      console.error("Microphone access denied", e);
      alert("Microphone access is required.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleSave = async () => {
    if (!audioBlob) return;
    setIsProcessing(true);
    try {
        await onUpload(audioBlob);
    } catch (e) {
        console.error(e);
    } finally {
        setIsProcessing(false);
    }
  };

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-surface border border-white/10 rounded-2xl shadow-2xl w-full max-w-md p-8 relative animate-scale-up">
        <button 
            onClick={onClose}
            className="absolute top-6 right-6 text-txt-tertiary hover:text-white transition-colors"
        >
            <X size={20} />
        </button>

        <h3 className="text-xl font-light text-white mb-8 flex items-center gap-3">
            <div className="p-2 bg-elevated rounded-lg text-accent">
                <Mic size={20} /> 
            </div>
            Voice Memo
        </h3>

        <div className="flex flex-col items-center justify-center space-y-8">
            <div className={`text-5xl font-mono font-light tracking-wider ${isRecording ? 'text-red-500 animate-pulse' : 'text-txt-primary'}`}>
                {formatTime(duration)}
            </div>

            {/* Visualizer Placeholder */}
            <div className="h-16 w-full bg-elevated border border-white/5 rounded-xl flex items-center justify-center gap-1 overflow-hidden px-4">
                {isRecording ? Array.from({length: 30}).map((_, i) => (
                    <div 
                        key={i} 
                        className="w-1.5 bg-red-500 rounded-full animate-bounce"
                        style={{ 
                            height: `${Math.random() * 60 + 20}%`, 
                            animationDelay: `${i * 0.05}s`,
                            opacity: Math.random() * 0.5 + 0.5
                        }}
                    />
                )) : (
                    <div className="text-xs text-txt-tertiary uppercase tracking-widest">Ready to Record</div>
                )}
            </div>

            <div className="flex gap-4 w-full">
                {!isRecording && !audioBlob && (
                    <button 
                        onClick={startRecording}
                        className="flex-1 flex items-center justify-center gap-2 px-6 py-4 bg-accent text-void font-bold rounded-xl hover:bg-white transition-all shadow-glow active:scale-95"
                    >
                        <Mic size={20} /> Start Recording
                    </button>
                )}

                {isRecording && (
                    <button 
                        onClick={stopRecording}
                        className="flex-1 flex items-center justify-center gap-2 px-6 py-4 bg-red-500 text-white font-bold rounded-xl hover:bg-red-600 transition-all shadow-[0_0_20px_rgba(239,68,68,0.4)] active:scale-95"
                    >
                        <Square size={20} fill="currentColor" /> Stop
                    </button>
                )}

                {!isRecording && audioBlob && (
                    <div className="flex gap-3 w-full">
                        <button 
                            onClick={() => { setAudioBlob(null); setDuration(0); }}
                            className="flex-1 px-4 py-3 text-txt-secondary hover:text-white bg-white/5 hover:bg-white/10 rounded-xl transition-colors font-medium"
                        >
                            Retake
                        </button>
                        <button 
                            onClick={handleSave}
                            disabled={isProcessing}
                            className="flex-[2] flex items-center justify-center gap-2 px-6 py-3 bg-emerald-600 text-white font-bold rounded-xl hover:bg-emerald-500 shadow-lg transition-all active:scale-95"
                        >
                            {isProcessing ? <Loader2 className="animate-spin" size={18}/> : <Save size={18} />}
                            {isProcessing ? "Processing..." : "Upload Memo"}
                        </button>
                    </div>
                )}
            </div>
        </div>
      </div>
    </div>
  );
};

export default VoiceRecorderModal;