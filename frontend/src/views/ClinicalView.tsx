import { useState, useEffect, useRef } from 'react';
import Sidebar from '../components/Sidebar';
import { useAppStore } from '../store/useAppStore';
import renderMarkdown from '../lib/markdown';
import { 
    Plus, X, Activity, Globe, Archive, ChevronLeft,
    AlertTriangle, Brain, Stethoscope, Pill, ArrowRightCircle, 
    Mic, StopCircle, FileText, RefreshCw, Menu, CheckCircle,
    Trash2, Sparkles, MessageSquare
} from 'lucide-react';
import { cn } from '../lib/utils';
import ConsultModal from '../components/ConsultModal';

// --- INTERFACES ---
interface CriticalAlert {
  alert: string;
  severity: 'CRITICAL' | 'URGENT' | 'IMPORTANT';
  action_required: string;
  time_sensitive: boolean;
  evidence?: string;
}

interface Differential {
  diagnosis: string;
  probability: number;
  status: 'CONFIRMED' | 'LIKELY' | 'POSSIBLE' | 'RULED_OUT';
  cant_miss: boolean;
}

interface DiagnosticTest {
  test: string;
  priority: 'IMMEDIATE' | 'URGENT' | 'ROUTINE';
  rationale: string;
  status: 'PENDING' | 'COMPLETED';
}

interface Treatment {
  intervention: string;
  dose: string;
  priority: 'IMMEDIATE' | 'URGENT';
}

interface DispositionGuidance {
  recommendation: 'ADMIT' | 'OBSERVATION' | 'DISCHARGE';
  reasoning: string;
}

interface ClinicalGuidance {
    critical_alerts?: CriticalAlert[];
    differential_diagnosis?: Differential[];
    suggested_workup?: DiagnosticTest[];
    recommended_treatments?: Treatment[];
    disposition_guidance?: DispositionGuidance;
}

// Simple Status Badge Component
const StatusBadge = ({ status }: { status: string }) => {
  const colors: Record<string, string> = {
    'Processing': 'bg-accent/10 text-accent border-accent/20 animate-pulse',
    'Ready': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    'Error': 'bg-red-500/10 text-red-400 border-red-500/20',
    'default': 'bg-white/5 text-txt-secondary border-white/10'
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${colors[status] || colors['default']}`}>
      {status || 'IDLE'}
    </span>
  );
};

export default function ClinicalView() {
  const { 
      erPatients: patients, 
      fetchERPatients: fetchPatients, 
      createERPatient: createPatient, 
      archivePatient, 
      deleteERPatient: deletePatient,
      currentChart: chartData, 
      fetchERChart: fetchChart,
      medicalSources, 
      fetchMedicalSources, 
      addMedicalSource, 
      deleteMedicalSource,
      submitERAudio,
      isSidebarOpen, 
      toggleSidebar
  } = useAppStore();

  // Local State
  const [activePatientId, setActivePatientId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [showNewPatientModal, setShowNewPatientModal] = useState(false);
  const [showSourcesModal, setShowSourcesModal] = useState(false);
  
  // Consult Modal State
  const [isConsultOpen, setIsConsultOpen] = useState(false);
  
  // Recording State
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<BlobPart[]>([]);

  // New Patient Form State
  const [newRoom, setNewRoom] = useState('');
  const [newAgeSex, setNewAgeSex] = useState('');
  const [newComplaint, setNewComplaint] = useState('');

  // Sources Form State
  const [newSourceName, setNewSourceName] = useState('');
  const [newSourceUrl, setNewSourceUrl] = useState('');

  // Mobile Tab State
  const [mobileTab, setMobileTab] = useState<'chart' | 'guidance'>('chart');

  // Polling for Patient List
  useEffect(() => {
    fetchPatients();
    const interval = setInterval(fetchPatients, 5000);
    return () => clearInterval(interval);
  }, [fetchPatients]);

  // Initial Fetch when selecting a patient
  useEffect(() => {
    if (activePatientId) {
      setLoading(true);
      fetchChart(activePatientId).finally(() => setLoading(false));
    }
  }, [activePatientId, fetchChart]);

  const activePatient = patients.find(p => p.id === activePatientId);

  // AUTO-REFRESH LOGIC: 
  // Watch the active patient's status. If it flips to 'Ready', fetch the new chart data.
  // This handles the "Push to frontend" requirement.
  useEffect(() => {
      if (activePatient?.status === 'Ready') {
          fetchChart(activePatient.id);
      }
  }, [activePatient?.status, activePatient?.id, fetchChart]);

  useEffect(() => {
    if (showSourcesModal) fetchMedicalSources();
  }, [showSourcesModal, fetchMedicalSources]);

  const handleCreatePatient = async () => {
    if (!newRoom || !newAgeSex || !newComplaint) return;
    await createPatient(newRoom, newAgeSex, newComplaint);
    setNewRoom(''); setNewAgeSex(''); setNewComplaint('');
    setShowNewPatientModal(false);
  };

  const handleAddSource = async () => {
    if (!newSourceName || !newSourceUrl) return;
    await addMedicalSource(newSourceName, newSourceUrl);
    setNewSourceName(''); setNewSourceUrl('');
  };

  // --- RECORDING LOGIC ---
  const startRecording = async (pid: number) => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const recorder = new MediaRecorder(stream);
        mediaRecorderRef.current = recorder;
        audioChunksRef.current = [];

        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunksRef.current.push(e.data);
        };

        recorder.onstop = async () => {
            const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
            await submitERAudio(pid, blob);
            stream.getTracks().forEach(t => t.stop());
            fetchPatients();
        };

        recorder.start();
        setIsRecording(true);
    } catch (e) {
        console.error("Microphone error:", e);
        alert("Microphone access needed.");
    }
  };

  const stopRecording = () => {
      if (mediaRecorderRef.current && isRecording) {
          mediaRecorderRef.current.stop();
          setIsRecording(false);
      }
  };

  // Helper to parse guidance JSON safely
  const getGuidance = (): ClinicalGuidance | null => {
    if (!chartData?.clinical_guidance_json) return null;
    try {
      return JSON.parse(chartData.clinical_guidance_json);
    } catch {
      return null;
    }
  };
  
  const guidance = getGuidance();

  return (
    // FIXED: Added 'flex' to root container so Sidebar and Content sit side-by-side on desktop
    <div className="flex fixed inset-0 w-full h-[100dvh] bg-void text-txt-primary overflow-hidden font-sans selection:bg-accent/20">
      <Sidebar isOpen={isSidebarOpen} setIsOpen={toggleSidebar} />
      
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full relative overflow-hidden min-w-0">
        
        {/* Top Bar / Header */}
        <div className="h-14 shrink-0 border-b border-white/5 flex items-center justify-between px-4 bg-void/80 backdrop-blur-md z-20">
            <div className="flex items-center gap-3 min-w-0">
                <button 
                    onClick={toggleSidebar} 
                    className="md:hidden p-2 -ml-2 text-txt-secondary hover:text-white rounded-lg transition-colors"
                >
                    <Menu className="w-5 h-5" />
                </button>
                <Activity className="text-accent animate-pulse-slow shrink-0" size={18} />
                <h1 className="font-bold text-sm tracking-wide text-white truncate">
                    ER TRACKER <span className="text-txt-tertiary font-normal ml-2 hidden sm:inline">| {patients.length} Active</span>
                </h1>
            </div>
            <div className="flex items-center gap-2 shrink-0">
                <button 
                    onClick={() => setShowSourcesModal(true)}
                    className="p-2 hover:bg-white/5 rounded-lg text-txt-tertiary hover:text-white transition-colors"
                    title="Manage Medical Sources"
                >
                    <Globe size={18} />
                </button>
                <button 
                    onClick={() => setShowNewPatientModal(true)}
                    className="flex items-center gap-2 bg-accent hover:bg-white text-void px-3 py-1.5 rounded-lg font-bold text-xs transition-all shadow-glow hover:shadow-glow-lg active:scale-95"
                >
                    <Plus size={14} strokeWidth={3} />
                    <span className="hidden sm:inline">NEW PATIENT</span>
                    <span className="sm:hidden">NEW</span>
                </button>
            </div>
        </div>

        <div className="flex-1 flex overflow-hidden relative">
            
            {/* Patient List (Left Column) */}
            <div className={cn(
                "border-r border-white/5 bg-elevated/10 flex flex-col z-10 bg-void transition-transform duration-300",
                // Mobile: Absolute inset to fill available space
                "absolute inset-0 w-full",
                // Desktop: Static sidebar width
                "md:static md:w-80 md:inset-auto",
                activePatientId ? "-translate-x-full md:translate-x-0" : "translate-x-0"
            )}>
                {/* overscroll-y-none prevents the rubber-band bounce on iOS */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-2 pb-32 overscroll-y-none touch-pan-y">
                    {patients.length === 0 && (
                        <div className="text-center py-20 text-txt-tertiary text-xs border-2 border-dashed border-white/5 rounded-xl m-2">
                            No active patients.
                        </div>
                    )}
                    {patients.map(p => (
                        <div 
                            key={p.id}
                            onClick={() => setActivePatientId(p.id)}
                            className={cn(
                                "p-4 rounded-xl cursor-pointer border transition-all group relative overflow-hidden",
                                activePatientId === p.id 
                                    ? "bg-accent/10 border-accent/30 shadow-inner-glow" 
                                    : "bg-surface border-transparent hover:bg-white/5 hover:border-white/5"
                            )}
                        >
                            <div className="flex justify-between items-start mb-1.5 relative z-10">
                                <div className="flex items-center gap-2">
                                    <span className={cn("font-bold text-lg font-mono", activePatientId === p.id ? "text-accent" : "text-white")}>{p.room_label}</span>
                                    <span className="text-xs font-bold bg-white/10 px-1.5 py-0.5 rounded text-txt-secondary">{p.age_sex}</span>
                                </div>
                                {/* STATUS INDICATOR: UPDATING... */}
                                {p.status === 'Processing' ? (
                                    <div className="flex items-center gap-1.5 animate-pulse">
                                        <Sparkles size={10} className="text-accent" />
                                        <span className="text-[10px] font-bold text-accent uppercase tracking-wider">Updating Chart...</span>
                                    </div>
                                ) : (
                                    <StatusBadge status={p.status || 'Ready'} />
                                )}
                            </div>
                            <div className="text-sm text-txt-secondary relative z-10 line-clamp-2 leading-relaxed">{p.chief_complaint}</div>
                            
                            {/* Actions: Visible on Hover OR if Active (Selected) */}
                            <div className={cn(
                                "absolute right-2 bottom-2 flex gap-1 transition-all z-20",
                                activePatientId === p.id 
                                    ? "opacity-100 translate-y-0" 
                                    : "opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0"
                            )}>
                                <button 
                                    onClick={(e) => { 
                                        e.stopPropagation(); 
                                        if (window.confirm("Delete this patient record permanently?")) deletePatient(p.id); 
                                    }}
                                    className="p-2 bg-red-500/10 text-red-400 border border-red-500/20 rounded-lg hover:bg-red-500 hover:text-white transition-colors backdrop-blur-md"
                                    title="Delete Permanently"
                                >
                                    <Trash2 size={14} />
                                </button>
                                <button 
                                    onClick={(e) => { e.stopPropagation(); archivePatient(p.id); }}
                                    className="p-2 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-lg hover:bg-blue-500 hover:text-white transition-colors backdrop-blur-md"
                                    title="Archive"
                                >
                                    <Archive size={14} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Active Patient View */}
            {activePatient ? (
                 <div className="flex-1 flex flex-col h-full overflow-hidden bg-void relative w-full min-w-0">
                    
                    {/* Patient Sticky Header */}
                    <div className="shrink-0 bg-surface/80 border-b border-white/5 p-3 backdrop-blur-md z-10 flex flex-col gap-3">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3 overflow-hidden">
                                <button onClick={() => setActivePatientId(null)} className="md:hidden p-2 -ml-2 text-txt-tertiary hover:text-white"><ChevronLeft size={20} /></button>
                                <div className="min-w-0">
                                    <h2 className="text-lg font-bold text-white flex items-center gap-2 truncate">
                                        Room {activePatient.room_label} 
                                        <span className="text-xs font-normal text-txt-tertiary bg-white/5 px-2 py-0.5 rounded-md border border-white/5">{activePatient.age_sex}</span>
                                    </h2>
                                    {/* HEADER STATUS: UPDATING... */}
                                    {activePatient.status === 'Processing' ? (
                                        <div className="flex items-center gap-2 mt-0.5 animate-pulse">
                                             <RefreshCw size={12} className="text-accent animate-spin" />
                                             <span className="text-xs font-bold text-accent uppercase tracking-wide">Updating Chart...</span>
                                        </div>
                                    ) : (
                                        <p className="text-txt-secondary text-xs truncate">{activePatient.chief_complaint}</p>
                                    )}
                                </div>
                            </div>
                            
                            <div className="flex items-center gap-2 shrink-0">
                                {/* CONSULT BUTTON - Bigger & spaced */}
                                <button 
                                    onClick={() => setIsConsultOpen(true)}
                                    className="flex items-center gap-2 bg-purple-500/10 text-purple-400 hover:bg-purple-500 hover:text-white px-5 py-3 rounded-xl font-bold text-sm transition-all border border-purple-500/20 active:scale-95 shadow-sm"
                                >
                                    <MessageSquare size={18} /> <span className="hidden sm:inline">CONSULT ATTENDING</span>
                                </button>

                                {/* DICTATE BUTTON - Bigger, spaced, margin-left applied */}
                                <div className="ml-4">
                                    {!isRecording ? (
                                        <button 
                                            onClick={() => startRecording(activePatient.id)}
                                            className="flex items-center gap-2 bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white px-5 py-3 rounded-xl font-bold text-sm transition-all border border-red-500/20 active:scale-95 shadow-sm"
                                        >
                                            <Mic size={18} /> <span className="hidden sm:inline">DICTATE</span>
                                        </button>
                                    ) : (
                                        <button 
                                            onClick={stopRecording}
                                            className="flex items-center gap-2 bg-red-500 text-white px-5 py-3 rounded-xl font-bold text-sm animate-pulse transition-all shadow-glow-red active:scale-95 shadow-sm"
                                        >
                                            <StopCircle size={18} /> <span className="hidden sm:inline">STOP</span>
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Mobile Tabs Segmented Control */}
                        <div className="flex md:hidden bg-black/20 p-1 rounded-xl border border-white/5">
                            <button 
                                onClick={() => setMobileTab('chart')}
                                className={cn(
                                    "flex-1 py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2",
                                    mobileTab === 'chart' ? "bg-accent text-void shadow-sm" : "text-txt-tertiary hover:text-white"
                                )}
                            >
                                <FileText size={14} /> Chart
                            </button>
                            <button 
                                onClick={() => setMobileTab('guidance')}
                                className={cn(
                                    "flex-1 py-2 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-2",
                                    mobileTab === 'guidance' ? "bg-accent text-void shadow-sm" : "text-txt-tertiary hover:text-white"
                                )}
                            >
                                <Brain size={14} /> Guidance
                            </button>
                        </div>
                    </div>

                    <div className="flex-1 overflow-hidden relative flex flex-col md:flex-row bg-black/20">
                        
                        {/* --- LEFT: LIVE CHART (Card Style) --- */}
                        <div className={cn(
                            "flex-1 flex flex-col min-h-0 transition-all",
                            mobileTab === 'chart' ? "flex" : "hidden md:flex"
                        )}>
                            <div className="flex-1 overflow-y-auto custom-scrollbar p-3 md:p-6 pb-32 overscroll-y-none touch-pan-y">
                                <div className="max-w-4xl mx-auto bg-surface border border-white/5 rounded-2xl shadow-sm min-h-full p-5 md:p-10 relative">
                                    
                                    <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/5">
                                        <h3 className="text-xs font-bold text-txt-tertiary uppercase tracking-widest flex items-center gap-2">
                                            <FileText size={14} className="text-accent" /> Live Chart
                                        </h3>
                                        {/* Fallback spinner if strictly loading via fetch, though Status covers most */}
                                        {loading && (
                                            <div className="flex items-center gap-2 text-xs text-accent">
                                                <RefreshCw size={12} className="animate-spin" /> Updating...
                                            </div>
                                        )}
                                    </div>

                                    {chartData ? (
                                        <div 
                                            className="prose prose-invert prose-sm max-w-none prose-headings:text-txt-primary prose-headings:font-semibold prose-headings:tracking-tight prose-p:text-txt-secondary prose-strong:text-white prose-li:text-txt-secondary"
                                            dangerouslySetInnerHTML={{ __html: renderMarkdown(chartData.chart_markdown) }} 
                                        />
                                    ) : (
                                        <div className="flex flex-col items-center justify-center py-32 opacity-30">
                                            <div className="w-20 h-20 rounded-full bg-white/5 flex items-center justify-center mb-4">
                                                <Activity size={32} />
                                            </div>
                                            <p className="font-medium text-lg">No chart data</p>
                                            <p className="text-sm">Dictate to generate a note.</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* --- RIGHT: CLINICAL GUIDANCE (Cards) --- */}
                        <div className={cn(
                            "w-full md:w-[400px] xl:w-[450px] flex-col border-l border-white/5 bg-elevated/5 min-h-0",
                            mobileTab === 'guidance' ? "flex flex-1" : "hidden md:flex"
                        )}>
                             <div className="p-4 border-b border-white/5 bg-surface/50 backdrop-blur-sm sticky top-0 z-10">
                                <h3 className="text-xs font-bold text-txt-tertiary uppercase tracking-widest flex items-center gap-2">
                                    <Brain size={14} className="text-purple-400" /> Clinical Partner
                                </h3>
                            </div>

                            <div className="flex-1 overflow-y-auto custom-scrollbar p-3 md:p-4 space-y-4 pb-32 overscroll-y-none touch-pan-y">
                                {!guidance ? (
                                    <div className="text-center py-20 text-txt-tertiary text-xs italic flex flex-col items-center gap-3 opacity-50">
                                        <CheckCircle size={24} />
                                        Awaiting AI analysis...
                                    </div>
                                ) : (
                                    <>
                                        {/* 1. Critical Alerts */}
                                        {guidance.critical_alerts?.map((alert: CriticalAlert, i: number) => (
                                            <div key={i} className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 animate-in slide-in-from-right-2 shadow-sm">
                                                <div className="flex items-start gap-3">
                                                    <div className="p-2 bg-red-500/20 rounded-lg shrink-0 text-red-400">
                                                        <AlertTriangle size={18} />
                                                    </div>
                                                    <div>
                                                        <h4 className="font-bold text-red-300 text-sm mb-1 leading-tight">{alert.alert}</h4>
                                                        <p className="text-xs text-red-200/70 mb-2 leading-relaxed">{alert.action_required}</p>
                                                        {alert.evidence && (
                                                            <div className="text-[10px] text-red-300/50 bg-black/20 px-2 py-1 rounded border border-white/5 inline-block">
                                                                {alert.evidence}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ))}

                                        {/* 2. Differentials */}
                                        <div className="space-y-2">
                                            <h4 className="text-[10px] font-bold text-txt-tertiary uppercase ml-1 tracking-widest">Differential Diagnosis</h4>
                                            {guidance.differential_diagnosis?.map((dx: Differential, i: number) => {
                                                const rawProb = Number(dx.probability);
                                                // FIXED: Strict clamping to 100% and better type handling
                                                const percent = rawProb <= 1 ? rawProb * 100 : rawProb;
                                                const probPercentage = Math.min(100, Math.round(percent));
                                                
                                                return (
                                                    <div key={i} className="bg-surface border border-white/5 rounded-xl p-3 flex items-center justify-between shadow-sm">
                                                        <div className="flex-1 min-w-0 pr-3">
                                                            <div className="font-bold text-sm text-white flex items-center gap-2 truncate">
                                                                {dx.diagnosis}
                                                                {dx.cant_miss && <span className="text-[9px] font-bold bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded border border-red-500/10 whitespace-nowrap">MUST RULE OUT</span>}
                                                            </div>
                                                            <div className="w-full h-1.5 bg-black/40 rounded-full mt-2 overflow-hidden">
                                                                <div 
                                                                    className={cn("h-full rounded-full transition-all duration-1000 ease-out", 
                                                                        probPercentage > 70 ? "bg-accent" : "bg-accent/50"
                                                                    )}
                                                                    style={{width: `${probPercentage}%`}} 
                                                                />
                                                            </div>
                                                        </div>
                                                        <div className="text-right shrink-0">
                                                            <div className="text-sm font-bold text-accent">{probPercentage}%</div>
                                                            <div className="text-[9px] font-medium text-txt-tertiary uppercase">{dx.status.replace('_', ' ')}</div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>

                                        {/* 3. Plan */}
                                        <div className="space-y-2">
                                            <h4 className="text-[10px] font-bold text-txt-tertiary uppercase ml-1 tracking-widest">Suggested Plan</h4>
                                            <div className="bg-surface border border-white/5 rounded-xl overflow-hidden shadow-sm">
                                                {guidance.suggested_workup?.map((test: DiagnosticTest, i: number) => (
                                                    <div key={i} className="p-3 border-b border-white/5 last:border-0 flex items-start gap-3">
                                                        <Stethoscope size={14} className="text-blue-400 mt-0.5 shrink-0" />
                                                        <div>
                                                            <div className="text-sm font-medium text-txt-primary leading-tight">{test.test}</div>
                                                            <div className="text-xs text-txt-tertiary mt-0.5 leading-snug opacity-80">{test.rationale}</div>
                                                        </div>
                                                    </div>
                                                ))}
                                                 {guidance.recommended_treatments?.map((tx: Treatment, i: number) => (
                                                    <div key={i} className="p-3 border-b border-white/5 last:border-0 flex items-start gap-3 bg-emerald-500/5">
                                                        <Pill size={14} className="text-emerald-400 mt-0.5 shrink-0" />
                                                        <div>
                                                            <div className="text-sm font-medium text-emerald-100 leading-tight">
                                                                {tx.intervention} <span className="text-emerald-400 ml-1 text-xs font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded">{tx.dose}</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>

                                        {/* 4. Disposition */}
                                        {guidance.disposition_guidance && (
                                            <div className="bg-purple-500/10 border border-purple-500/20 rounded-xl p-4 shadow-sm">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <ArrowRightCircle className="text-purple-400" size={16} />
                                                    <span className="font-bold text-purple-200 text-sm">DISPOSITION: {guidance.disposition_guidance.recommendation}</span>
                                                </div>
                                                <p className="text-xs text-purple-200/70 leading-relaxed">{guidance.disposition_guidance.reasoning}</p>
                                            </div>
                                        )}
                                        
                                        <div className="h-10" />
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            ) : (
                /* No Patient Selected Empty State */
                <div className="flex-1 flex flex-col items-center justify-center text-txt-tertiary bg-void">
                    <div className="w-24 h-24 rounded-full bg-surface border border-white/5 flex items-center justify-center mb-6 shadow-glow">
                        <Activity className="w-10 h-10 text-accent opacity-50" />
                    </div>
                    <p className="text-lg font-light text-white">No Patient Selected</p>
                    <p className="text-sm text-txt-secondary mt-2">Select a patient from the list or create a new one.</p>
                </div>
            )}
        </div>

        {/* --- MODALS --- */}
        
        <ConsultModal 
            isOpen={isConsultOpen}
            onClose={() => setIsConsultOpen(false)}
            patientId={activePatientId}
            roomNumber={activePatient?.room_label || 'Unknown'}
        />

        {/* New Patient Modal */}
        {showNewPatientModal && (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
                <div className="bg-surface border border-white/10 rounded-2xl w-full max-w-md p-6 shadow-2xl animate-scale-up">
                    <div className="flex justify-between items-center mb-6 border-b border-white/5 pb-4">
                        <h3 className="text-lg font-bold text-white flex items-center gap-2">
                            <Plus size={18} className="text-accent" /> New Patient
                        </h3>
                        <button onClick={() => setShowNewPatientModal(false)} className="p-1 text-txt-tertiary hover:text-white bg-white/5 rounded-full"><X size={18} /></button>
                    </div>
                    <div className="space-y-5">
                        <div>
                            <label className="text-[10px] font-bold text-txt-tertiary uppercase tracking-widest mb-1.5 block">Room Number</label>
                            <input autoFocus className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-accent outline-none transition-colors" placeholder="e.g. 12" value={newRoom} onChange={e => setNewRoom(e.target.value)} />
                        </div>
                        <div>
                            <label className="text-[10px] font-bold text-txt-tertiary uppercase tracking-widest mb-1.5 block">Age / Sex</label>
                            <input className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-accent outline-none transition-colors" placeholder="e.g. 45M" value={newAgeSex} onChange={e => setNewAgeSex(e.target.value)} />
                        </div>
                        <div>
                            <label className="text-[10px] font-bold text-txt-tertiary uppercase tracking-widest mb-1.5 block">Chief Complaint</label>
                            <input className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-accent outline-none transition-colors" placeholder="e.g. Chest Pain" value={newComplaint} onChange={e => setNewComplaint(e.target.value)} />
                        </div>
                        <button 
                            onClick={handleCreatePatient} 
                            disabled={!newRoom || !newAgeSex || !newComplaint}
                            className="w-full bg-accent hover:bg-white text-void font-bold py-4 rounded-xl mt-2 transition-all shadow-glow active:scale-95 disabled:opacity-50 disabled:active:scale-100"
                        >
                            Start Chart
                        </button>
                    </div>
                </div>
            </div>
        )}

        {/* Sources Modal */}
        {showSourcesModal && (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
                <div className="bg-surface border border-white/10 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl animate-scale-up">
                    <div className="p-6 border-b border-white/10 flex justify-between items-center shrink-0">
                        <h3 className="text-lg font-bold text-white flex items-center gap-2"><Globe size={20} className="text-accent" /> Medical Knowledge Sources</h3>
                        <button onClick={() => setShowSourcesModal(false)} className="p-1 text-txt-tertiary hover:text-white bg-white/5 rounded-full"><X size={18} /></button>
                    </div>
                    
                    <div className="p-6 border-b border-white/10 bg-black/20 shrink-0">
                        <div className="flex gap-3">
                            <input placeholder="Source Name (e.g. WikEM)" className="flex-1 bg-elevated border border-white/5 rounded-xl px-4 py-3 text-white focus:border-accent outline-none text-sm" value={newSourceName} onChange={e => setNewSourceName(e.target.value)} />
                            <input placeholder="Domain (e.g. wikem.org)" className="flex-[2] bg-elevated border border-white/5 rounded-xl px-4 py-3 text-white focus:border-accent outline-none text-sm" value={newSourceUrl} onChange={e => setNewSourceUrl(e.target.value)} />
                            <button onClick={handleAddSource} disabled={!newSourceName || !newSourceUrl} className="px-6 bg-white/10 hover:bg-accent hover:text-void rounded-xl transition-all font-bold text-sm disabled:opacity-50">Add</button>
                        </div>
                        <p className="text-xs text-txt-tertiary mt-3 ml-1">Restricts the "Clinical" persona to search only these high-trust domains.</p>
                    </div>

                    <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-2">
                        {medicalSources.length === 0 && <div className="text-center py-10 text-txt-tertiary">No custom sources defined.</div>}
                        {medicalSources.map(s => (
                            <div key={s.id} className="flex items-center justify-between p-4 rounded-xl bg-elevated/50 border border-white/5 hover:border-white/10 transition-colors group">
                                <div className="flex items-center gap-4">
                                    <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center text-accent"><Globe size={18} /></div>
                                    <div><div className="font-bold text-sm text-white">{s.name}</div><div className="text-xs text-txt-tertiary font-mono">{s.url_pattern}</div></div>
                                </div>
                                <button onClick={() => deleteMedicalSource(s.id)} className="p-2 text-txt-tertiary hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100"><Trash2 size={16} /></button>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        )}

      </div>
    </div>
  );
};