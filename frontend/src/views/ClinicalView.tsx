import React, { useState, useEffect, useRef } from 'react';
import Sidebar from '../components/Sidebar';
import { useAppStore, ERPatient, ERChart } from '../store/useAppStore';
import renderMarkdown from '../lib/markdown';
import { useNavigate } from 'react-router-dom';
import { 
    Plus, X, Activity, Settings, Mic, StopCircle, RefreshCw, Trash2, Globe, Archive, ChevronLeft,
    AlertTriangle, Brain, Stethoscope, Pill, ArrowRightCircle, CheckCircle, Clock
} from 'lucide-react';
import { cn } from '../lib/utils';
import { toast } from 'react-toastify';

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
  return_precautions?: string;
}

interface ClinicalGuidance {
  critical_alerts: CriticalAlert[];
  differential_diagnosis: Differential[];
  diagnostic_plan: DiagnosticTest[];
  treatment_recommendations: Treatment[];
  disposition_guidance: DispositionGuidance;
}

// --- COMPONENTS ---

const DictationRecorder: React.FC<{ pid: number; onUpload: () => void }> = ({ pid, onUpload }) => {
    const { submitERAudio } = useAppStore();
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<BlobPart[]>([]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorderRef.current = new MediaRecorder(stream);
            chunksRef.current = [];
            
            mediaRecorderRef.current.ondataavailable = (e) => chunksRef.current.push(e.data);
            mediaRecorderRef.current.onstop = async () => {
                const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
                setIsProcessing(true);
                await submitERAudio(pid, blob);
                setIsProcessing(false);
                onUpload();
                toast.success("Dictation sent to AI Scribe");
                stream.getTracks().forEach(t => t.stop());
            };
            
            mediaRecorderRef.current.start();
            setIsRecording(true);
        } catch (e) {
            console.error(e);
            toast.error("Microphone access failed");
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    return (
        <button 
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isProcessing}
            className={cn(
                "flex items-center gap-3 px-6 py-4 rounded-2xl transition-all shadow-lg active:scale-95 w-full justify-center font-bold tracking-wide uppercase text-sm",
                isRecording 
                    ? "bg-red-500 text-white animate-pulse" 
                    : isProcessing 
                        ? "bg-surface text-txt-tertiary cursor-wait"
                        : "bg-accent text-void hover:bg-white"
            )}
        >
            {isRecording ? <StopCircle size={20} /> : <Mic size={20} />}
            {isRecording ? "Stop Recording" : isProcessing ? "Processing..." : "Start Dictation"}
        </button>
    );
};

// --- ENHANCED HEADER ---
interface HeaderProps {
    patient: ERPatient;
    onClose: () => void;
    onArchive: () => void;
    onDelete: () => void;
}

const EnhancedHeader: React.FC<HeaderProps> = ({ patient, onClose, onArchive, onDelete }) => {
    const arrival = new Date(patient.created_at);
    const now = new Date();
    const diffMs = now.getTime() - arrival.getTime();
    const diffHrs = Math.floor(diffMs / 3600000);
    const diffMins = Math.floor((diffMs % 3600000) / 60000);

    return (
        <div className="h-auto md:h-20 py-4 px-6 border-b border-white/5 flex flex-col md:flex-row items-start md:items-center justify-between shrink-0 bg-surface/50 backdrop-blur-md gap-4">
            <div className="flex items-center gap-4 flex-1 overflow-hidden">
                <div className="w-10 h-10 rounded-lg bg-accent text-void flex items-center justify-center font-bold text-lg shadow-glow shrink-0">
                    {patient.room_label}
                </div>
                <div className="min-w-0">
                    <h2 className="text-xl font-medium text-white flex items-center gap-2 truncate">
                        <span className="truncate">{patient.age_sex} • {patient.chief_complaint}</span>
                    </h2>
                    <div className="flex items-center gap-3 text-xs text-txt-secondary mt-0.5">
                        <span className="flex items-center gap-1 shrink-0">
                            <Clock size={12} className="text-accent" />
                            LOS: {diffHrs}h {diffMins}m
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-white/5 border border-white/5 shrink-0">
                            Acuity: {patient.acuity_level || 3}
                        </span>
                    </div>
                </div>
            </div>
            
            <div className="flex items-center gap-2 md:gap-3 self-end md:self-auto">
                <button 
                    onClick={onDelete}
                    className="p-2 md:p-2.5 text-txt-tertiary hover:text-red-500 hover:bg-red-500/10 rounded-xl transition-colors"
                    title="Delete Record"
                >
                    <Trash2 size={20} />
                </button>
                <button 
                    onClick={onArchive} 
                    className="p-2 md:p-2.5 text-txt-tertiary hover:text-accent hover:bg-accent/10 rounded-xl transition-colors"
                    title="Archive Patient"
                >
                    <Archive size={20} />
                </button>
                <button 
                    onClick={onClose} 
                    className="p-2 md:p-2.5 text-txt-tertiary hover:text-white hover:bg-white/10 rounded-xl transition-colors"
                    title="Close Chart"
                >
                    <X size={24} />
                </button>
            </div>
        </div>
    );
};

// --- CLINICAL GUIDANCE PANEL ---
const GuidancePanel: React.FC<{ chart: ERChart | null }> = ({ chart }) => {
    if (!chart) return (
        <div className="flex-1 flex items-center justify-center text-txt-tertiary text-sm">
            Waiting for AI analysis...
        </div>
    );

    let guidance: ClinicalGuidance;
    try {
        if (chart.clinical_guidance_json) {
            guidance = JSON.parse(chart.clinical_guidance_json);
        } else {
            throw new Error("No JSON");
        }
    } catch {
        // FALLBACK for legacy or failed JSON
        const legacyDiffs = chart.differentials ? JSON.parse(chart.differentials) : [];
        const legacyPearls = chart.clinical_pearls ? JSON.parse(chart.clinical_pearls) : [];
        
        guidance = {
            critical_alerts: legacyPearls.map((p: string) => ({ alert: p, severity: 'IMPORTANT', action_required: 'Review', time_sensitive: false })),
            differential_diagnosis: legacyDiffs.map((d: string) => ({ diagnosis: d, probability: 50, status: 'POSSIBLE', cant_miss: false })),
            diagnostic_plan: [],
            treatment_recommendations: [],
            disposition_guidance: { recommendation: 'OBSERVATION', reasoning: 'Pending full analysis.' }
        };
    }

    return (
        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar space-y-6">
            
            {/* 1. CRITICAL ALERTS */}
            {guidance.critical_alerts && guidance.critical_alerts.length > 0 && (
                <section className="space-y-3">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-red-400 flex items-center gap-2">
                        <AlertTriangle size={12} /> Critical Alerts
                    </h3>
                    {guidance.critical_alerts.map((alert, i) => (
                        <div key={i} className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 shadow-sm relative overflow-hidden">
                            <div className="absolute left-0 top-0 bottom-0 w-1 bg-red-500" />
                            <p className="text-sm font-medium text-red-100 mb-1">{alert.alert}</p>
                            <p className="text-xs text-red-300/80 uppercase font-bold tracking-wide flex items-center gap-2">
                                <ArrowRightCircle size={10} /> {alert.action_required}
                            </p>
                        </div>
                    ))}
                </section>
            )}

            {/* 2. DIFFERENTIALS */}
            {guidance.differential_diagnosis && (
                <section className="space-y-3">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-txt-tertiary flex items-center gap-2">
                        <Brain size={12} /> Differential Diagnosis
                    </h3>
                    <div className="space-y-2">
                        {guidance.differential_diagnosis.map((diff, i) => (
                            <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-elevated border border-white/5">
                                <div className="flex items-center gap-3">
                                    {diff.cant_miss && <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" title="Can't Miss" />}
                                    <span className={cn("text-sm", diff.cant_miss ? "font-medium text-white" : "text-txt-secondary")}>
                                        {diff.diagnosis}
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="h-1 w-16 bg-white/5 rounded-full overflow-hidden">
                                        <div className="h-full bg-accent/50" style={{ width: `${diff.probability}%` }} />
                                    </div>
                                    <span className="text-[10px] text-txt-tertiary w-8 text-right">{diff.probability}%</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {/* 3. DIAGNOSTIC PLAN */}
            {guidance.diagnostic_plan && guidance.diagnostic_plan.length > 0 && (
                <section className="space-y-3">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-txt-tertiary flex items-center gap-2">
                        <Stethoscope size={12} /> Workup Plan
                    </h3>
                    <div className="space-y-2">
                        {guidance.diagnostic_plan.map((test, i) => (
                            <div key={i} className="flex items-center gap-3 p-3 rounded-lg border border-white/5 bg-surface hover:bg-elevated transition-colors">
                                <div className={cn(
                                    "w-2 h-2 rounded-full",
                                    test.status === 'COMPLETED' ? "bg-green-500" : "bg-yellow-500"
                                )} />
                                <div className="flex-1">
                                    <p className="text-sm text-txt-primary">{test.test}</p>
                                    <p className="text-[10px] text-txt-tertiary">{test.rationale}</p>
                                </div>
                                {test.priority === 'IMMEDIATE' && (
                                    <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 text-[10px] font-bold">NOW</span>
                                )}
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {/* 4. TREATMENT RECOMMENDATIONS */}
            {guidance.treatment_recommendations && guidance.treatment_recommendations.length > 0 && (
                <section className="space-y-3">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-txt-tertiary flex items-center gap-2">
                        <Pill size={12} /> Treatments
                    </h3>
                    <div className="space-y-2">
                        {guidance.treatment_recommendations.map((tx, i) => (
                            <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
                                <div>
                                    <p className="text-sm font-medium text-emerald-100">{tx.intervention}</p>
                                    <p className="text-[10px] text-emerald-400/80">{tx.dose}</p>
                                </div>
                                {tx.priority === 'IMMEDIATE' && <span className="text-[10px] font-bold text-red-400">STAT</span>}
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {/* 5. DISPOSITION */}
            {guidance.disposition_guidance && (
                <section className="p-4 rounded-xl bg-blue-500/5 border border-blue-500/10">
                    <h3 className="text-[10px] font-bold uppercase tracking-widest text-blue-400 mb-2 flex items-center gap-2">
                        <CheckCircle size={12} /> Disposition
                    </h3>
                    <div className="flex items-center gap-3 mb-2">
                        <span className="text-lg font-bold text-white">{guidance.disposition_guidance.recommendation}</span>
                    </div>
                    <p className="text-xs text-txt-secondary leading-relaxed">
                        {guidance.disposition_guidance.reasoning}
                    </p>
                </section>
            )}
        </div>
    );
};

// --- MAIN VIEW ---

const ClinicalView: React.FC = () => {
  const navigate = useNavigate();
  const { 
    erPatients, fetchERPatients, createERPatient, 
    currentChart, fetchERChart, archivePatient, deleteERPatient,
    medicalSources, fetchMedicalSources, addMedicalSource, deleteMedicalSource
  } = useAppStore();
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isNewPatientOpen, setIsNewPatientOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState<ERPatient | null>(null);
  const [agentStatus, setAgentStatus] = useState<string>("");

  // Forms
  const [newRoom, setNewRoom] = useState('');
  const [newComplaint, setNewComplaint] = useState('');
  const [newAge, setNewAge] = useState('');
  const [newGender, setNewGender] = useState('M');
  const [newSourceName, setNewSourceName] = useState('');
  const [newSourceUrl, setNewSourceUrl] = useState('');

  // Polling
  useEffect(() => {
    fetchERPatients();
    const interval = setInterval(fetchERPatients, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (selectedPatient) {
        fetchERChart(selectedPatient.id);
        const interval = setInterval(() => fetchERChart(selectedPatient.id), 3000); 
        return () => clearInterval(interval);
    }
  }, [selectedPatient]);

  // Status Polling
  useEffect(() => {
      if (!selectedPatient) return;
      const pollStatus = async () => {
          try {
              const res = await fetch(`/api/er/status/${selectedPatient.id}`);
              const data = await res.json();
              if (data.status && data.status !== "Idle") setAgentStatus(data.status);
              else setAgentStatus("");
          } catch (e) { console.error(e); }
      };
      const interval = setInterval(pollStatus, 1000);
      return () => clearInterval(interval);
  }, [selectedPatient]);

  const handleCreate = async () => {
      if (!newRoom || !newComplaint || !newAge) return;
      await createERPatient(newRoom, newComplaint, `${newAge}${newGender}`);
      setIsNewPatientOpen(false);
      setNewRoom(''); setNewComplaint(''); setNewAge('');
      toast.success("Patient Admitted");
  };

  const handleAddSource = async () => {
      if (!newSourceName || !newSourceUrl) return;
      await addMedicalSource(newSourceName, newSourceUrl);
      setNewSourceName(''); setNewSourceUrl('');
  };

  const handleArchive = async () => {
      if (!selectedPatient) return;
      await archivePatient(selectedPatient.id);
      setSelectedPatient(null);
      toast.success("Patient Archived");
  };

  const handleDelete = async () => {
      if (!selectedPatient) return;
      if (confirm("Permanently delete this patient and all records?")) {
          await deleteERPatient(selectedPatient.id);
          setSelectedPatient(null);
          toast.success("Patient Deleted");
      }
  };

  return (
    <div className="flex h-screen bg-void text-txt-primary overflow-hidden font-sans">
      <div className="hidden md:flex w-64 flex-col fixed inset-y-0 z-50">
        <Sidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />
      </div>

      <div className="flex-1 flex flex-col md:pl-64 h-full relative">
        {/* Removed MobileNav per request */}
        
        <main className="flex-1 overflow-y-auto p-4 md:p-8 custom-scrollbar">
            {/* Header */}
            <div className="flex justify-between items-center mb-6 md:mb-8">
                <div className="flex items-center gap-4">
                    <button 
                        onClick={() => navigate('/')} 
                        className="p-2 -ml-2 text-txt-secondary hover:text-white hover:bg-white/10 rounded-full transition-colors"
                        title="Back to Chat"
                    >
                        <ChevronLeft size={28} />
                    </button>
                    <div>
                        <h1 className="text-2xl md:text-3xl font-light tracking-tight text-white mb-1">Emergency Room</h1>
                        <p className="text-txt-secondary text-xs md:text-sm">Active Patient Board • {erPatients.length} Active</p>
                    </div>
                </div>
                <div className="flex gap-2 md:gap-3">
                    <button onClick={() => { fetchMedicalSources(); setIsSettingsOpen(true); }} className="p-3 bg-surface hover:bg-elevated rounded-xl border border-white/5 transition-all text-txt-secondary hover:text-white">
                        <Settings size={20} />
                    </button>
                    <button onClick={() => setIsNewPatientOpen(true)} className="flex items-center gap-2 bg-accent hover:bg-white text-void px-4 py-3 rounded-xl font-bold transition-all shadow-glow active:scale-95">
                        <Plus size={20} />
                        <span className="hidden md:inline">New Patient</span>
                        <span className="md:hidden">New</span>
                    </button>
                </div>
            </div>

            {/* Patient Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 md:gap-4 pb-20">
                {erPatients.map(p => (
                    <div 
                        key={p.id} 
                        onClick={() => setSelectedPatient(p)}
                        className="bg-surface border border-white/5 p-3 md:p-4 rounded-xl hover:border-accent/30 transition-all cursor-pointer group flex flex-col justify-between h-32 md:h-auto"
                    >
                        {/* Improved Card Header */}
                        <div className="flex justify-between items-start mb-2">
                             <div className="flex items-center gap-2 md:gap-3">
                                <div className="w-8 h-8 md:w-10 md:h-10 rounded-lg bg-elevated flex items-center justify-center text-sm md:text-lg font-bold text-txt-primary border border-white/5 shrink-0">
                                    {p.room_label}
                                </div>
                                <div>
                                    <h3 className="text-sm md:text-base font-medium text-white leading-tight">{p.age_sex}</h3>
                                    <div className="text-[10px] text-txt-tertiary mt-0.5">
                                        {new Date(p.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                    </div>
                                </div>
                            </div>
                            <Activity size={16} className="text-accent opacity-50 group-hover:opacity-100 transition-opacity" />
                        </div>
                        
                        <p className="text-xs md:text-sm text-txt-tertiary line-clamp-2 md:line-clamp-3 leading-relaxed">
                            {p.chief_complaint}
                        </p>
                    </div>
                ))}
                {erPatients.length === 0 && <div className="col-span-full py-20 text-center text-txt-tertiary font-light">No active patients.</div>}
            </div>
        </main>

        {/* --- MODALS --- */}

        {isNewPatientOpen && (
            <div className="fixed inset-0 z-[60] flex items-center justify-center bg-void/90 backdrop-blur-sm p-4 animate-fade-in">
                <div className="bg-surface p-8 rounded-[32px] border border-border-subtle w-full max-w-lg shadow-2xl flex flex-col relative animate-slide-up">
                    <button onClick={() => setIsNewPatientOpen(false)} className="absolute top-6 right-6 text-txt-tertiary hover:text-white"><X size={24} /></button>
                    <h2 className="text-2xl font-light text-white mb-6">New Patient</h2>
                    <div className="space-y-4">
                        <div>
                            <label className="text-[10px] font-bold text-txt-tertiary uppercase tracking-wider mb-2 block">Room</label>
                            <input value={newRoom} onChange={(e) => setNewRoom(e.target.value)} className="w-full bg-elevated border-none rounded-xl px-4 py-3 text-white focus:ring-1 focus:ring-accent outline-none" placeholder="e.g. 10" />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="text-[10px] font-bold text-txt-tertiary uppercase tracking-wider mb-2 block">Age</label>
                                <input value={newAge} onChange={(e) => setNewAge(e.target.value)} className="w-full bg-elevated border-none rounded-xl px-4 py-3 text-white focus:ring-1 focus:ring-accent outline-none" placeholder="45" type="number" />
                            </div>
                            <div>
                                <label className="text-[10px] font-bold text-txt-tertiary uppercase tracking-wider mb-2 block">Sex</label>
                                <select value={newGender} onChange={(e) => setNewGender(e.target.value)} className="w-full bg-elevated border-none rounded-xl px-4 py-3 text-white focus:ring-1 focus:ring-accent outline-none"><option value="M">Male</option><option value="F">Female</option></select>
                            </div>
                        </div>
                        <div>
                            <label className="text-[10px] font-bold text-txt-tertiary uppercase tracking-wider mb-2 block">Chief Complaint</label>
                            <input value={newComplaint} onChange={(e) => setNewComplaint(e.target.value)} className="w-full bg-elevated border-none rounded-xl px-4 py-3 text-white focus:ring-1 focus:ring-accent outline-none" placeholder="e.g. Chest Pain" />
                        </div>
                    </div>
                    <div className="flex gap-4 justify-end mt-8"><button onClick={handleCreate} className="bg-accent text-void hover:bg-white px-8 py-3 rounded-xl font-bold transition-all shadow-glow active:scale-95">Admit</button></div>
                </div>
            </div>
        )}

        {/* 2. PATIENT CHART (Split View) */}
        {selectedPatient && (
            <div className="fixed inset-0 z-[60] bg-void/95 backdrop-blur-md flex flex-col animate-fade-in">
                
                {/* Header (Enhanced) with embedded controls */}
                <EnhancedHeader 
                    patient={selectedPatient} 
                    onClose={() => setSelectedPatient(null)}
                    onArchive={handleArchive}
                    onDelete={handleDelete}
                />

                {/* Content */}
                <div className="flex-1 flex overflow-hidden flex-col md:flex-row">
                    
                    {/* Left: The Chart */}
                    <div className="flex-1 overflow-y-auto p-4 md:p-8 md:border-r border-white/5 custom-scrollbar">
                        <div className="max-w-3xl mx-auto space-y-8">
                            {currentChart ? (
                                <div 
                                    className="markdown-body prose prose-invert prose-p:text-txt-secondary prose-headings:text-txt-primary prose-strong:text-white max-w-none text-sm md:text-base"
                                    dangerouslySetInnerHTML={{ __html: renderMarkdown(currentChart.chart_markdown) }}
                                />
                            ) : (
                                <div className="flex flex-col items-center justify-center h-64 text-txt-tertiary">
                                    <RefreshCw className="animate-spin mb-4" />
                                    <p>Initializing Chart...</p>
                                </div>
                            )}
                            <div className="h-20" />
                        </div>
                    </div>

                    {/* Right: The Brain (Guidance) */}
                    <div className="h-[40vh] md:h-auto md:w-[450px] bg-surface/30 flex flex-col border-t md:border-t-0 md:border-l border-white/5 backdrop-blur-xl">
                        <GuidancePanel chart={currentChart} />

                        {/* Dictation Bar */}
                        <div className="p-4 md:p-6 border-t border-white/5 bg-void">
                            {agentStatus && (
                                <div className="mb-4 flex items-center justify-center gap-2 animate-pulse text-accent text-xs font-mono uppercase tracking-widest">
                                    <RefreshCw size={12} className="animate-spin" />
                                    {agentStatus}
                                </div>
                            )}
                            <DictationRecorder pid={selectedPatient.id} onUpload={() => {}} />
                            <p className="text-center text-[10px] text-txt-tertiary mt-3 uppercase tracking-widest">
                                Dictate HPI, Exam, or Plan
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        )}

        {/* 3. SETTINGS */}
        {isSettingsOpen && (
            <div className="fixed inset-0 z-[70] flex items-center justify-center bg-void/90 backdrop-blur-sm p-4 animate-fade-in">
                <div className="bg-surface p-8 rounded-[32px] border border-border-subtle w-full max-w-2xl shadow-2xl flex flex-col max-h-[85vh] animate-slide-up">
                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-xl font-light text-txt-primary">Clinical Knowledge Sources</h2>
                        <button onClick={() => setIsSettingsOpen(false)} className="text-txt-secondary hover:text-white transition-colors"><X size={24} /></button>
                    </div>
                    <div className="bg-elevated/50 p-4 rounded-xl border border-white/5 mb-6 text-sm text-txt-secondary flex items-start gap-3">
                        <Globe className="shrink-0 text-accent mt-0.5" size={16} />
                        <p>The AI Scribe uses these trusted domains to research guidelines and verify your treatment plans via RAG.</p>
                    </div>
                    <div className="flex gap-3 mb-8">
                        <input placeholder="Name" className="flex-1 bg-elevated border-none rounded-xl px-4 py-3 text-white focus:ring-1 focus:ring-accent outline-none text-sm" value={newSourceName} onChange={e => setNewSourceName(e.target.value)} />
                         <input placeholder="Domain" className="flex-[2] bg-elevated border-none rounded-xl px-4 py-3 text-white focus:ring-1 focus:ring-accent outline-none text-sm" value={newSourceUrl} onChange={e => setNewSourceUrl(e.target.value)} />
                        <button onClick={handleAddSource} className="px-5 bg-white/5 hover:bg-accent hover:text-void rounded-xl transition-colors font-bold text-sm">Add</button>
                    </div>
                    <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2">
                        {medicalSources.map(s => (
                            <div key={s.id} className="flex items-center justify-between p-4 rounded-xl bg-elevated border border-white/5 hover:border-white/10 transition-colors">
                                <div className="flex items-center gap-3"><div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-txt-tertiary"><Globe size={14} /></div><div><div className="font-bold text-sm text-white">{s.name}</div><div className="text-xs text-txt-tertiary">{s.url_pattern}</div></div></div>
                                <button onClick={() => deleteMedicalSource(s.id)} className="p-2 text-txt-tertiary hover:text-red-400 transition-colors"><Trash2 size={16} /></button>
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

export default ClinicalView;