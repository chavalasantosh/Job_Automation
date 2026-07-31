import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Activity, 
  Terminal, 
  Shield, 
  Power, 
  CheckCircle2, 
  XCircle, 
  Zap,
  LayoutDashboard,
  BarChart3,
  Settings,
  MonitorPlay,
  Cpu
} from 'lucide-react';
import { motion as Motion } from 'framer-motion';
import axios from 'axios';

const API_BASE = "http://localhost:8000/api";
const WS_URL = "ws://localhost:8000/ws/logs";
const RELAY_BASE = "http://localhost:8000/relay/view";

function App() {
  const [agents, setAgents] = useState([]);
  const [stats, setStats] = useState({ total_applications: 0, success_rate: 0, failed: 0 });
  const [logs, setLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('fleet');
  const logEndRef = useRef(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/fleet`);
      setAgents(res.data);
    } catch (e) { console.error("API error", e); }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/stats`);
      setStats(res.data);
    } catch (e) { console.error("Stats error", e); }
  }, []);

  useEffect(() => {
    const initialStatusTimeout = setTimeout(fetchStatus, 0);
    const initialStatsTimeout = setTimeout(fetchStats, 0);
    const statusInterval = setInterval(fetchStatus, 3000);
    const statsInterval = setInterval(fetchStats, 5000);

    const ws = new WebSocket(WS_URL);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const newLogs = Array.isArray(data) ? data : [data];
      setLogs((prev) => [...prev, ...newLogs].slice(-100));
    };

    return () => {
      clearTimeout(initialStatusTimeout);
      clearTimeout(initialStatsTimeout);
      clearInterval(statusInterval);
      clearInterval(statsInterval);
      ws.close();
    };
  }, [fetchStatus, fetchStats]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="min-h-screen bg-[#050507] text-[#e0e0e0] flex overflow-hidden">
      {/* Sidebar */}
      <nav className="w-20 lg:w-64 border-r border-white/5 bg-[#0a0a0c] flex flex-col p-6 space-y-8 shadow-[10px_0_30px_rgba(0,0,0,0.5)] z-20">
        <div className="flex items-center space-x-3 mb-10">
          <div className="w-10 h-10 bg-accent rounded-lg flex items-center justify-center shadow-[0_0_20px_rgba(59,130,246,0.3)]">
            <Shield className="text-white" size={24} />
          </div>
          <span className="hidden lg:block font-orbitron font-bold text-xl tracking-tighter neon-text">NOWCURRY</span>
        </div>
        
        <div className="flex-1 space-y-4">
          <NavItem icon={<LayoutDashboard size={20}/>} label="Fleet Monitor" active={activeTab === 'fleet'} onClick={() => setActiveTab('fleet')} />
          <NavItem icon={<MonitorPlay size={20}/>} label="Theater Mode" active={activeTab === 'theater'} onClick={() => setActiveTab('theater')} />
          <NavItem icon={<Terminal size={20}/>} label="Live Telemetry" active={activeTab === 'logs'} onClick={() => setActiveTab('logs')} />
          <NavItem icon={<BarChart3 size={20}/>} label="Analytics" active={activeTab === 'stats'} onClick={() => setActiveTab('stats')} />
          <NavItem icon={<Settings size={20}/>} label="Protocols" active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} />
        </div>

        <div className="pt-8 border-t border-white/5 text-xs text-center text-white/30 font-orbitron">
          INFINITY v2.0
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 p-8 overflow-y-auto custom-scrollbar bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.05),transparent_40%)]">
        <header className="flex justify-between items-start mb-12">
          <div>
            <h1 className="text-3xl font-orbitron font-bold mb-2 tracking-widest text-shadow-sm">OPERATIONS CENTER</h1>
            <p className="text-white/40 text-sm flex items-center gap-2">
              <Activity size={14} className="text-neon animate-pulse" /> 
              ALL SYSTEMS AUTONOMOUS | ZERO INTERVENTION PROTOCOL ACTIVE
            </p>
          </div>
          <div className="flex gap-4">
            <StatCard label="Success Rate" value={`${stats.success_rate.toFixed(1)}%`} icon={<Zap size={16} className="text-yellow-400"/>}/>
            <StatCard label="Active missions" value={agents.filter(a => a.status === 'ACTIVE').length} icon={<Cpu size={16} className="text-accent"/>}/>
          </div>
        </header>

        {activeTab === 'fleet' && (
          <Motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
          >
            {agents.map((agent) => (
              <AgentCard 
                key={agent.id}
                name={agent.portal} 
                status={agent.status} 
                id={agent.id}
                mission={agent.current_mission}
              />
            ))}
          </Motion.div>
        )}

        {activeTab === 'theater' && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
            {agents.filter(a => a.status === 'BUSY' || a.status === 'ACTIVE').map(agent => (
              <VisualMissionCard key={agent.id} agent={agent} />
            ))}
            {agents.filter(a => a.status === 'BUSY' || a.status === 'ACTIVE').length === 0 && (
              <div className="col-span-2 h-[400px] border-2 border-dashed border-white/5 rounded-3xl flex flex-col items-center justify-center text-white/20">
                <MonitorPlay size={64} className="mb-4 opacity-20" />
                <p className="font-orbitron tracking-widest">AWAITING LIVE MISSION STREAM</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'logs' && (
          <Motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="h-[70vh] bg-black/40 border border-white/5 rounded-2xl p-6 font-mono text-sm overflow-hidden flex flex-col shadow-inner"
          >
            <div className="flex items-center gap-2 mb-4 text-white/40">
              <Terminal size={14} /> 
              <span>TERMINAL_OUTPUT_STREAM</span>
            </div>
            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1">
              {logs.map((log, i) => (
                <div key={i} className={`flex gap-3 ${log.level === 'ERROR' ? 'text-red-400' : 'text-white/70'}`}>
                  <span className="text-white/20">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                  <span className={`${log.agent === 'Naukri' ? 'text-blue-400' : 'text-purple-400'} font-bold w-20`}>{log.agent}</span>
                  <span>{log.message}</span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </Motion.div>
        )}
      </main>
    </div>
  );
}

function VisualMissionCard({ agent }) {
  const [refresh, setRefresh] = useState(0);
  
  useEffect(() => {
    const interval = setInterval(() => setRefresh(r => r + 1), 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="bg-[#0f0f13] border border-white/10 rounded-3xl overflow-hidden shadow-2xl"
    >
      <div className="p-4 border-b border-white/5 flex justify-between items-center bg-black/20">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="font-orbitron text-xs font-bold tracking-tighter">LIVE FEED: {agent.id}</span>
        </div>
        <span className="text-[10px] text-white/30 uppercase">{agent.current_mission || 'Processing...'}</span>
      </div>
      <div className="aspect-video bg-black flex items-center justify-center relative group">
        <img 
          src={`${RELAY_BASE}/${agent.id}_latest.png?r=${refresh}`} 
          alt="Mission Visual"
          className="w-full h-full object-cover opacity-80"
          onError={(e) => { e.target.src = "https://via.placeholder.com/800x450/000?text=SIGNAL_LOST"; }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent pointer-events-none" />
        <div className="absolute bottom-4 left-4 right-4 flex justify-between items-end">
          <div className="space-y-1">
             <p className="text-[10px] text-accent font-bold uppercase tracking-widest">Agent Activity</p>
             <p className="text-xs font-medium text-white/70 italic">"Autonomous decision via Gemini Vision"</p>
          </div>
          <div className="w-12 h-12 rounded-full border border-white/10 flex items-center justify-center animate-spin-slow">
            <Shield size={20} className="text-accent/50" />
          </div>
        </div>
      </div>
    </Motion.div>
  );
}

function NavItem({ icon, label, active, onClick }) {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center space-x-4 p-3 rounded-xl transition-all duration-300 ${active ? 'bg-accent/10 text-accent border border-accent/20 shadow-[0_0_15px_rgba(59,130,246,0.1)]' : 'text-white/40 hover:bg-white/5 hover:text-white'}`}
    >
      {icon}
      <span className="hidden lg:block font-medium tracking-tight whitespace-nowrap">{label}</span>
    </button>
  );
}

function StatCard({ label, value, icon }) {
  return (
    <div className="bg-card/20 border border-white/5 rounded-xl px-6 py-3 flex items-center gap-4 hover:border-white/10 transition-colors">
      <div className="p-2 bg-white/5 rounded-lg">{icon}</div>
      <div>
        <p className="text-[10px] uppercase text-white/30 font-orbitron tracking-tighter">{label}</p>
        <p className="text-lg font-bold font-orbitron text-shadow-sm">{value}</p>
      </div>
    </div>
  );
}

function AgentCard({ name, status, id, mission }) {
  const isActive = status === 'ACTIVE' || status === 'BUSY';
  return (
    <div className={`glass-card p-6 flex flex-col space-y-4 transition-all duration-500 border border-white/5 relative overflow-hidden ${isActive ? 'neon-border bg-accent/5' : 'grayscale-[0.5] opacity-80 bg-white/2'}`}>
      <div className="flex justify-between items-start">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center font-bold text-xl ${isActive ? 'bg-accent text-white shadow-[0_0_20px_rgba(59,130,246,0.3)]' : 'bg-white/5 text-white/20'}`}>
            {name[0]}
          </div>
          <div>
            <h3 className="font-bold text-lg font-orbitron tracking-tight">{name}</h3>
            <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase font-bold tracking-widest ${isActive ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
              {status}
            </span>
          </div>
        </div>
        <div className="text-[10px] text-white/20 font-mono">
          ID: {id.slice(0, 8)}
        </div>
      </div>
      
      <div className="bg-black/20 p-3 rounded-lg border border-white/5">
         <p className="text-[10px] text-white/20 mb-1 uppercase font-orbitron">Current Mission</p>
         <p className="text-xs text-white/70 truncate">{mission || 'No active objective'}</p>
      </div>

      <div className="grid grid-cols-2 gap-3 text-[10px] font-orbitron text-white/40">
        <div className="bg-black/20 p-2 rounded-lg">
          <p>LOAD</p>
          <p className="text-white">{isActive ? '34%' : '0%'}</p>
        </div>
        <div className="bg-black/20 p-2 rounded-lg">
          <p>NETWORK</p>
          <p className="text-white">ENCRYPTED</p>
        </div>
      </div>
    </div>
  );
}

export default App;
