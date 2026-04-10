import { useState, useEffect } from 'react';
import { getHealth, submitTicket, getTickets } from './api';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { LayoutDashboard, Ticket, Server, Activity, Search, X, CheckCircle, AlertCircle, BrainCircuit } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

function App() {
  const [view, setView] = useState('customer');
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    getHealth().then(status => setIsOnline(status));
  }, []);

  return (
    <div className="app-container">
      <Sidebar view={view} setView={setView} isOnline={isOnline} />
      <main className="main-content">
        <AnimatePresence mode="wait">
          {view === 'customer' ? (
            <motion.div key="customer" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.3 }}>
              <CustomerPortal />
            </motion.div>
          ) : (
            <motion.div key="admin" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.3 }}>
              <AdminDashboard />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}

function Sidebar({ view, setView, isOnline }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-title">
        <BrainCircuit size={32} color="#60a5fa" />
        PortalOS
      </div>
      <div className="nav-buttons">
        <button className={`nav-btn ${view === 'customer' ? 'active' : ''}`} onClick={() => setView('customer')}>
          <Ticket size={20} /> Submit Ticket
        </button>
        <button className={`nav-btn ${view === 'admin' ? 'active' : ''}`} onClick={() => setView('admin')}>
          <LayoutDashboard size={20} /> Admin Dashboard
        </button>
      </div>
      <div className="sidebar-footer">
        <div className={`status-indicator ${isOnline ? 'online' : 'offline'}`}>
          <Activity size={18} /> {isOnline ? 'Core Systems Online' : 'Systems Offline'}
        </div>
      </div>
    </aside>
  );
}

function CustomerPortal() {
  const [formData, setFormData] = useState({ name: '', email: '', subject: '', desc: '' });
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (formData.desc.length < 10) return setErrorMsg("Description too short. Please provide at least 10 characters.");
    
    setLoading(true);
    try {
      const res = await submitTicket({
        customer_name: formData.name,
        customer_email: formData.email,
        subject: formData.subject,
        description: formData.desc,
        language: "en",
        source_channel: "react_web"
      });
      setSuccessMsg(`Ticket #${res.ticket_id} securely submitted! AI Routing active.`);
      setFormData({ name: '', email: '', subject: '', desc: '' });
      setErrorMsg(null);
    } catch {
      setErrorMsg("Connection failure. The backend might be unreachable.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="view-wrapper">
      <div className="page-header">
        <div>
           <h1 className="page-title">Support Center</h1>
           <p className="page-subtitle">Describe your issue and our AI routing engine handles the rest seamlessly.</p>
        </div>
      </div>
      
      <AnimatePresence>
        {successMsg && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="alert-success">
            <CheckCircle size={20} /> {successMsg}
          </motion.div>
        )}
        {errorMsg && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="alert-error">
            <AlertCircle size={20} /> {errorMsg}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="card">
        <form onSubmit={handleSubmit} className="form-grid">
          <div className="form-group">
            <label>Full Name</label>
            <input required placeholder="Jane Doe" value={formData.name} onChange={e=>setFormData({...formData, name: e.target.value})} />
          </div>
          <div className="form-group">
            <label>Email Address</label>
            <input required type="email" placeholder="jane@example.com" value={formData.email} onChange={e=>setFormData({...formData, email: e.target.value})} />
          </div>
          <div className="form-group form-full">
            <label>Issue Subject</label>
            <input required placeholder="E.g., Missing items in order" value={formData.subject} onChange={e=>setFormData({...formData, subject: e.target.value})} />
          </div>
          <div className="form-group form-full">
            <label>Detailed Description</label>
            <textarea required rows={5} placeholder="Provide specifics about the problem..." value={formData.desc} onChange={e=>setFormData({...formData, desc: e.target.value})} />
          </div>
          <div className="form-group form-full">
            <button type="submit" className="submit-btn" disabled={loading}>
              {loading ? <><div className="spinner"></div> Authenticating & Routing...</> : "Submit Ticket Now"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AdminDashboard() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTicket, setSelectedTicket] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const tickets = await getTickets();
      setData(tickets);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  if (loading) return <div style={{ fontSize: '1.2rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '1rem' }}><div className="spinner"></div> Syncing Real-Time Feed...</div>;
  if (!data.length) return <div style={{ fontSize: '1.2rem', color: '#94a3b8' }}>No active tickets found in the database.</div>;

  // Compute metrics
  const total = data.length;
  const escalated = data.filter(t => t.routing?.escalated).length;
  const confidences = data.map(t => t.prediction?.category_confidence).filter(Boolean);
  const avgConf = confidences.length ? (confidences.reduce((a,b)=>a+b,0) / confidences.length * 100).toFixed(1) : "0";

  // Compute Pie Chart Data (Priorities)
  const pMap = { Critical: 0, High: 0, Medium: 0, Low: 0 };
  data.forEach(t => {
      const p = t.routing?.priority || 'medium';
      const cap = p.charAt(0).toUpperCase() + p.slice(1);
      if (pMap[cap] !== undefined) pMap[cap]++;
  });
  const priorityData = Object.keys(pMap).filter(k => pMap[k]>0).map(k => ({ name: k, value: pMap[k] }));
  const COLORS = { Critical: '#ef4444', High: '#f97316', Medium: '#10b981', Low: '#94a3b8' };

  // Compute Bar Chart Data (Categories)
  const catMap = {};
  data.forEach(t => {
    const cat = t.prediction?.predicted_category || 'Unknown';
    catMap[cat] = (catMap[cat] || 0) + 1;
  });
  const catData = Object.keys(catMap).map(cat => ({ name: cat, Count: catMap[cat] })).sort((a,b) => b.Count - a.Count).slice(0, 5);

  // Filter Data
  const filteredData = data.filter(t => {
    const query = searchQuery.toLowerCase();
    return t.ticket_id.toString().includes(query) || 
           t.customer_name.toLowerCase().includes(query) || 
           (t.prediction?.predicted_category && t.prediction.predicted_category.toLowerCase().includes(query)) ||
           (t.routing?.assigned_queue && t.routing.assigned_queue.toLowerCase().includes(query));
  });

  return (
    <div className="view-wrapper">
      <div className="page-header mt-4">
        <div>
          <h1 className="page-title">Analytics Dashboard</h1>
          <p className="page-subtitle">Real-time overview of global ticket volumes and ML predictions.</p>
        </div>
        <button onClick={fetchData} className="action-btn">🔄 Refresh Data</button>
      </div>

      <div className="metrics-grid">
        <motion.div className="metric-card" whileHover={{ y: -5 }}>
          <div className="metric-label">Global Volume</div>
          <div className="metric-value">{total}</div>
        </motion.div>
        <motion.div className="metric-card" whileHover={{ y: -5 }}>
          <div className="metric-label">ML Escalations</div>
          <div className="metric-value">{escalated}</div>
          {escalated > 0 && <div style={{position: 'absolute', top: '1.5rem', right: '1.5rem', width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444', boxShadow: '0 0 10px #ef4444'}}></div>}
        </motion.div>
        <motion.div className="metric-card" whileHover={{ y: -5 }}>
          <div className="metric-label">A.I. Precision</div>
          <div className="metric-value" style={{color: avgConf > 80 ? '#10b981' : '#f97316'}}>{avgConf}%</div>
        </motion.div>
        <motion.div className="metric-card" whileHover={{ y: -5 }}>
          <div className="metric-label">High Priority Unresolved</div>
          <div className="metric-value">{pMap.Critical + pMap.High}</div>
        </motion.div>
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <div className="chart-title">Priorities Distribution</div>
          <ResponsiveContainer width="100%" height="80%">
            <PieChart>
              <defs>
                <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="4" stdDeviation="6" floodOpacity="0.1" />
                </filter>
              </defs>
              <Pie 
                 data={priorityData} cx="50%" cy="50%" 
                 innerRadius={75} outerRadius={115} 
                 paddingAngle={5} dataKey="value" stroke="none" filter="url(#shadow)"
                 label={{fill: '#475569', fontSize: 13, fontWeight: 500}}>
                {priorityData.map((e, idx) => <Cell key={`cell-${idx}`} fill={COLORS[e.name]} />)}
              </Pie>
              <Tooltip contentStyle={{backgroundColor: '#ffffff', border: '1px solid #e2e8f0', shadow: '0 10px 15px -3px rgba(0,0,0,0.1)', borderRadius: '12px', color: '#0f172a', fontWeight: 600}} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-card">
          <div className="chart-title">Top Predicted Categories</div>
          <ResponsiveContainer width="100%" height="80%">
            <BarChart data={catData} layout="vertical" margin={{ top: 0, right: 30, left: 30, bottom: 0 }}>
              <defs>
                <linearGradient id="colorCount" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.8}/>
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={1}/>
                </linearGradient>
              </defs>
              <XAxis type="number" stroke="#94a3b8" tick={{fontSize: 12, fill: '#64748b'}} />
              <YAxis type="category" dataKey="name" width={100} fontSize={13} fontWeight={500} stroke="#475569" />
              <Tooltip cursor={{fill: '#f8fafc'}} contentStyle={{backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)'}} />
              <Bar dataKey="Count" fill="url(#colorCount)" radius={[0, 6, 6, 0]} barSize={24} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="table-container">
        <div className="table-header-options" style={{padding: '1.5rem'}}>
          <h3 className="chart-title" style={{margin: 0}}>Ticket Feed</h3>
          <div style={{position: 'relative'}}>
            <Search size={18} style={{position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b'}} />
            <input 
              type="text" 
              className="search-input" 
              placeholder="Search ID, Name, or Intent..." 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Customer Name</th>
              <th>AI Category</th>
              <th>Confidence</th>
              <th>Assigned Queue</th>
              <th>Priority</th>
            </tr>
          </thead>
          <tbody>
            {filteredData.map(t => {
              const p = t.routing?.priority || 'medium';
              const pCap = p.charAt(0).toUpperCase() + p.slice(1);
              return (
                <tr key={t.ticket_id} onClick={() => setSelectedTicket(t)}>
                  <td><span style={{color: '#94a3b8'}}>#</span>{t.ticket_id}</td>
                  <td style={{fontWeight: 500}}>{t.customer_name}</td>
                  <td>{t.prediction?.predicted_category}</td>
                  <td>{t.prediction?.category_confidence ? (t.prediction.category_confidence * 100).toFixed(1) + '%' : '-'}</td>
                  <td>{t.routing?.assigned_queue}</td>
                  <td><span className={`badge ${p.toLowerCase()}`}>{pCap}</span></td>
                </tr>
              )
            })}
            {filteredData.length === 0 && (
              <tr>
                <td colSpan="6" style={{textAlign: 'center', padding: '3rem', color: '#64748b'}}>No tickets match your search constraint.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <AnimatePresence>
        {selectedTicket && (
          <TicketDrawer ticket={selectedTicket} onClose={() => setSelectedTicket(null)} />
        )}
      </AnimatePresence>

    </div>
  );
}

function TicketDrawer({ ticket, onClose }) {
  const p = ticket.routing?.priority || 'medium';
  const pCap = p.charAt(0).toUpperCase() + p.slice(1);
  return (
    <div className="drawer-overlay" onClick={onClose}>
      <motion.div 
        className="drawer-content" 
        onClick={e => e.stopPropagation()}
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      >
        <div className="drawer-header">
           <h2 style={{fontFamily: 'Outfit', color: '#0f172a', fontSize: '1.25rem'}}>Ticket Details <span style={{color: '#94a3b8', fontWeight: 400}}>#{ticket.ticket_id}</span></h2>
           <button className="drawer-close" onClick={onClose}><X size={24} /></button>
        </div>
        <div className="drawer-body">
           <div className="ticket-detail-item">
             <div className="ticket-detail-label">Customer</div>
             <div className="ticket-detail-value">
                <span style={{fontWeight: 600}}>{ticket.customer_name}</span> &lt;{ticket.customer_email}&gt;
             </div>
           </div>
           
           <div className="ticket-detail-item">
             <div className="ticket-detail-label">Subject</div>
             <div className="ticket-detail-value" style={{fontWeight: 600}}>{ticket.subject}</div>
           </div>

           <div className="ticket-detail-item">
             <div className="ticket-detail-label">Description Payload</div>
             <div className="ticket-detail-value" style={{color: '#475569'}}>{ticket.description}</div>
           </div>

           <div className="ai-reasoning-box">
             <div className="ai-reasoning-title">
                <BrainCircuit size={22} /> Deep Dive: AI Inference & Metrics
             </div>
             
             <div className="ai-reasoning-grid">
                <div className="ai-stat-box">
                  <div className="ticket-detail-label">Predicted Intent</div>
                  <div style={{color: '#0f172a', fontWeight: 700, fontSize: '1.05rem', marginBottom: '0.75rem'}}>
                    {ticket.prediction?.predicted_intent || 'Unknown'}
                  </div>
                  
                  <div className="ticket-detail-label">Prediction Confidence (Intent)</div>
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', fontWeight: 600}}>
                     <span>{ticket.prediction?.intent_confidence ? (ticket.prediction.intent_confidence*100).toFixed(1) : 0}%</span>
                  </div>
                  <div className="progress-container">
                     <div className={`progress-fill ${ticket.prediction?.intent_confidence > 0.8 ? 'green' : ticket.prediction?.intent_confidence > 0.5 ? 'orange' : 'red'}`} style={{width: `${(ticket.prediction?.intent_confidence || 0) * 100}%`}}></div>
                  </div>
                </div>

                <div className="ai-stat-box">
                  <div className="ticket-detail-label">Primary Category</div>
                  <div style={{color: '#0f172a', fontWeight: 700, fontSize: '1.05rem', marginBottom: '0.75rem'}}>
                    {ticket.prediction?.predicted_category || 'Unknown'}
                  </div>

                  <div className="ticket-detail-label">Prediction Confidence (Category)</div>
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', fontWeight: 600}}>
                     <span>{ticket.prediction?.category_confidence ? (ticket.prediction.category_confidence*100).toFixed(1) : 0}%</span>
                  </div>
                  <div className="progress-container">
                     <div className={`progress-fill ${ticket.prediction?.category_confidence > 0.8 ? 'green' : ticket.prediction?.category_confidence > 0.5 ? 'orange' : 'red'}`} style={{width: `${(ticket.prediction?.category_confidence || 0) * 100}%`}}></div>
                  </div>
                </div>
             </div>
             
             <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem'}}>
                 <div className="ai-stat-box" style={{background: '#ffffff'}}>
                    <div className="ticket-detail-label">Model Specs</div>
                    <div style={{fontSize: '0.9rem', color: '#334155'}}><b>Version:</b> {ticket.prediction?.model_version || 'v1.0.0'}</div>
                    <div style={{fontSize: '0.9rem', color: '#334155'}}><b>Latency:</b> {ticket.prediction?.inference_time_ms ? `${ticket.prediction.inference_time_ms} ms` : 'N/A'}</div>
                 </div>
                 
                 <div className="ai-stat-box" style={{background: '#ffffff'}}>
                    <div className="ticket-detail-label" style={{marginBottom: '0.75rem'}}>Top Alternative Categories</div>
                    <div className="alt-category-list">
                       {ticket.prediction?.top_categories?.slice(1, 4).map((altCat, i) => (
                           <div key={i} className="alt-category-item">
                               <span style={{fontWeight: 500}}>{altCat.category}</span>
                               <span style={{color: '#94a3b8'}}>{(altCat.confidence * 100).toFixed(1)}%</span>
                           </div>
                       )) || <div style={{fontSize: '0.85rem', color: '#94a3b8'}}>No alternative data available.</div>}
                    </div>
                 </div>
             </div>

             <div className="ticket-detail-item" style={{marginBottom: '0', padding: '1.25rem', background: '#f8fafc', borderRadius: '0.75rem', border: '1px solid #cbd5e1'}}>
               <div className="ticket-detail-label">Deterministic Rule Flag triggered</div>
               <div style={{color: '#0f172a', fontSize: '0.95rem', fontWeight: 500}}>{ticket.routing?.reason}</div>
             </div>
           </div>
        </div>
        <div style={{padding: '1.5rem 2rem', borderTop: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
           <div>
             <span className="ticket-detail-label" style={{marginRight: '1rem'}}>Current Priority:</span>
             <span className={`badge ${p.toLowerCase()}`}>{pCap}</span>
           </div>
           <button className="submit-btn" style={{width: 'auto', padding: '0.75rem 1.5rem', marginTop: 0}}>Take Action</button>
        </div>
      </motion.div>
    </div>
  );
}

export default App;
