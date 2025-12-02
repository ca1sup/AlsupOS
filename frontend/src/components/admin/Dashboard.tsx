import React, { useEffect, useState, useRef } from 'react';
import renderMarkdown from '../../lib/markdown';
import { Activity, Calendar, CheckSquare, CreditCard, Sparkles, Headphones, Loader2, StopCircle, RefreshCw } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, CartesianGrid, Tooltip, YAxis } from 'recharts';
import { useAppStore } from '../../store/useAppStore';
import { toast } from 'react-toastify';

interface DashboardData {
  suggestions?: { content_private: string };
  tasks: any[];
  events: any[];
  finance?: any;
}

const Dashboard: React.FC = () => {
  const { runJob } = useAppStore();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [loadingAudio, setLoadingAudio] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const loadData = async () => {
    try {
      const res = await fetch('/api/steward/dashboard');
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    return () => { if(audioRef.current) audioRef.current.pause(); };
  }, []);

  const handleRegenerate = async () => {
    if (isRegenerating) return;
    setIsRegenerating(true);
    toast.info("Generating new briefing... (this takes ~10s)");
    
    try {
        await runJob();
        // Wait 10s for the LLM to finish (local inference takes time)
        // Then refresh the data
        setTimeout(async () => {
            await loadData();
            toast.success("Briefing updated.");
            setIsRegenerating(false);
        }, 10000);
    } catch (e) {
        console.error(e);
        toast.error("Failed to trigger generation.");
        setIsRegenerating(false);
    }
  };

  const handlePlayBriefing = async () => {
    if (audioPlaying && audioRef.current) {
        audioRef.current.pause();
        setAudioPlaying(false);
        return;
    }
    setLoadingAudio(true);
    try {
      const res = await fetch('/api/steward/audio-briefing');
      if (!res.ok) throw new Error("Audio fetch failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      
      setAudioPlaying(true);
      audio.play();
      audio.onended = () => {
        setAudioPlaying(false);
        URL.revokeObjectURL(url);
      };
    } catch (e) {
      console.error("TTS Error", e);
      alert("Failed to generate audio briefing.");
    } finally {
      setLoadingAudio(false);
    }
  };

  if (loading) return <div className="p-12 text-center text-txt-tertiary font-sans animate-pulse">Initializing Command Center...</div>;
  if (!data) return <div className="p-12 text-center text-txt-tertiary font-sans">Dashboard unavailable.</div>;

  const healthData = [
    { name: 'Mon', score: 75 },
    { name: 'Tue', score: 82 },
    { name: 'Wed', score: 78 },
    { name: 'Thu', score: 88 },
    { name: 'Fri', score: 85 },
    { name: 'Sat', score: 90 },
    { name: 'Sun', score: 87 },
  ];

  return (
    <div className="space-y-8 animate-slide-up">
      <header className="mb-10 border-b border-border-invisible pb-8">
        <h1 className="text-4xl font-light text-txt-primary tracking-tight">Command Center</h1>
        <p className="text-txt-secondary mt-2 font-light">Overview of your digital estate.</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Daily Briefing */}
        <div className="lg:col-span-2 bg-surface rounded-[24px] p-8 border border-border-invisible shadow-float hover:border-border-subtle transition-all duration-500">
          <div className="flex items-center justify-between mb-6 border-b border-border-invisible pb-4">
            <div className="flex items-center gap-4">
                <div className="p-3 bg-elevated rounded-2xl text-accent">
                <Sparkles className="w-5 h-5" />
                </div>
                <h2 className="text-xl font-light text-txt-primary">Daily Briefing</h2>
            </div>
            <button 
                onClick={handleRegenerate}
                disabled={isRegenerating}
                className="p-2 text-txt-tertiary hover:text-accent hover:bg-elevated rounded-xl transition-all active:scale-95 disabled:opacity-50"
                title="Regenerate Briefing"
            >
                <RefreshCw className={`w-5 h-5 ${isRegenerating ? 'animate-spin' : ''}`} />
            </button>
          </div>
          
          <div 
            className="prose prose-invert prose-p:text-txt-body prose-headings:text-txt-primary max-w-none leading-relaxed min-h-[100px]"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(data.suggestions?.content_private || 'No suggestions for today.') }}
          />
          
          <div className="mt-8 pt-6 border-t border-border-invisible flex justify-end gap-3">
             <button 
               onClick={handlePlayBriefing}
               disabled={loadingAudio}
               className="flex items-center gap-3 px-6 py-3 bg-elevated hover:bg-border-active rounded-full text-sm font-bold text-txt-primary transition-all active:scale-95 disabled:opacity-50 shadow-sm"
             >
                {loadingAudio ? <Loader2 className="w-4 h-4 animate-spin" /> : (audioPlaying ? <StopCircle className="w-4 h-4" /> : <Headphones className="w-4 h-4" />)}
                {audioPlaying ? "Stop Audio" : "Read Aloud"}
             </button>
          </div>
        </div>

        {/* Health Chart */}
        <div className="bg-surface rounded-[24px] p-8 border border-border-invisible shadow-float flex flex-col hover:border-border-subtle transition-all duration-500">
          <div className="flex items-center gap-4 mb-6 border-b border-border-invisible pb-4">
            <div className="p-3 bg-elevated rounded-2xl text-accent">
              <Activity className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-light text-txt-primary">Health Trend</h2>
          </div>
          <div className="flex-1 min-h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={healthData}>
                <defs>
                  <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff8a65" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#ff8a65" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#2a2a2a" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fontSize: 11, fill: '#707070'}} />
                <YAxis hide domain={[60, 100]} />
                <Tooltip 
                    contentStyle={{ backgroundColor: '#1a1a1a', borderColor: '#2a2a2a', color: '#ffffff', borderRadius: '12px' }}
                    itemStyle={{ color: '#ff8a65' }}
                />
                <Area type="monotone" dataKey="score" stroke="#ff8a65" strokeWidth={2} fillOpacity={1} fill="url(#colorScore)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pending Tasks */}
        <div className="bg-surface rounded-[24px] p-8 border border-border-invisible shadow-float hover:border-border-subtle transition-all duration-500">
          <div className="flex items-center gap-4 mb-6 border-b border-border-invisible pb-4">
             <div className="p-3 bg-elevated rounded-2xl text-accent">
              <CheckSquare className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-light text-txt-primary">Pending Tasks</h2>
          </div>
          <ul className="space-y-4">
            {data.tasks.slice(0, 5).map((task: any, i: number) => (
              <li key={i} className="flex items-start gap-4 text-sm text-txt-secondary group">
                <input type="checkbox" className="mt-1 rounded-full border-border-active bg-input text-accent focus:ring-0 cursor-pointer" />
                <span className="group-hover:text-txt-primary transition-colors leading-relaxed">{task.description}</span>
              </li>
            ))}
            {data.tasks.length === 0 && <li className="text-txt-tertiary text-sm italic">No pending tasks.</li>}
          </ul>
        </div>

        {/* Events */}
        <div className="bg-surface rounded-[24px] p-8 border border-border-invisible shadow-float hover:border-border-subtle transition-all duration-500">
          <div className="flex items-center gap-4 mb-6 border-b border-border-invisible pb-4">
             <div className="p-3 bg-elevated rounded-2xl text-accent">
              <Calendar className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-light text-txt-primary">Upcoming Events</h2>
          </div>
          <ul className="space-y-5">
            {data.events.slice(0, 5).map((evt: any, i: number) => (
              <li key={i} className="flex flex-col gap-1 border-l-2 border-border-active pl-4 hover:border-accent transition-colors">
                <span className="text-sm font-medium text-txt-primary">{evt.title}</span>
                <span className="text-xs text-txt-tertiary">
                  {new Date(evt.start_time).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}
                </span>
              </li>
            ))}
             {data.events.length === 0 && <li className="text-txt-tertiary text-sm italic">No upcoming events.</li>}
          </ul>
        </div>

        {/* Finance */}
        <div className="bg-surface rounded-[24px] p-8 border border-border-invisible shadow-float hover:border-border-subtle transition-all duration-500">
          <div className="flex items-center gap-4 mb-6 border-b border-border-invisible pb-4">
             <div className="p-3 bg-elevated rounded-2xl text-accent">
              <CreditCard className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-light text-txt-primary">Finance Snapshot</h2>
          </div>
          <div className="text-sm text-txt-secondary">
             {data.finance ? (
               <div className="flex flex-col gap-4">
                 <div className="flex justify-between items-end">
                   <span className="text-xs font-bold uppercase tracking-widest text-txt-tertiary">Budget Used</span>
                   <span className="font-medium text-txt-primary text-lg">{data.finance.budget_used || '0%'}</span>
                 </div>
                 <div className="h-3 w-full bg-input rounded-full overflow-hidden">
                   <div className="h-full bg-accent shadow-[0_0_10px_rgba(255,138,101,0.4)]" style={{ width: data.finance.budget_used || '0%' }}></div>
                 </div>
                 <p className="mt-2 text-xs leading-relaxed text-txt-tertiary">{data.finance.summary || 'Financial sync pending.'}</p>
               </div>
             ) : (
               <p className="italic text-txt-tertiary">No finance data available.</p>
             )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default Dashboard;