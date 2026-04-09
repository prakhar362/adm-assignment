import { useState, useEffect } from 'react';
import { getHealth, submitTicket, getTickets } from './api';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { LayoutDashboard, Ticket, Server, Activity } from 'lucide-react';

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
        {view === 'customer' ? <CustomerPortal /> : <AdminDashboard />}
      </main>
    </div>
  );
}

function Sidebar({ view, setView, isOnline }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-title">
        <Server size={28} color="#3b82f6" />
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
          <Activity size={16} /> {isOnline ? 'Core Systems Online' : 'Systems Offline'}
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
    if (formData.desc.length < 10) return setErrorMsg("Description too short.");
    
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
      setSuccessMsg(`Ticket #${res.ticket_id} securely submitted! Routing active.`);
      setFormData({ name: '', email: '', subject: '', desc: '' });
      setErrorMsg(null);
    } catch {
      setErrorMsg("Connection failure.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="view-wrapper">
      <div className="page-header">
        <h1 className="page-title">Support Center</h1>
        <p className="page-subtitle">Describe your issue and our AI routing engine handles the rest.</p>
      </div>
      
      {successMsg && <div className="alert-success">{successMsg}</div>}
      {errorMsg && <div className="alert-error">{errorMsg}</div>}

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
            <input required placeholder="Short summary" value={formData.subject} onChange={e=>setFormData({...formData, subject: e.target.value})} />
          </div>
          <div className="form-group form-full">
            <label>Detailed Description</label>
            <textarea required rows={5} placeholder="Provide specifics..." value={formData.desc} onChange={e=>setFormData({...formData, desc: e.target.value})} />
          </div>
          <div className="form-group form-full">
            <button type="submit" className="submit-btn" disabled={loading}>
              {loading ? "Authenticating..." : "Submit Ticket Immediately"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AdminDashboard() {
  const [data, setData] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);

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

  if (loading) return <div>Compiling Analytics...</div>;
  if (!data.length) return <div>No active tickets found.</div>;

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
  const COLORS = { Critical: '#ef4444', High: '#f97316', Medium: '#10b981', Low: '#64748b' };

  // Compute Bar Chart Data (Categories)
  const catMap = {};
  data.forEach(t => {
    const cat = t.prediction?.predicted_category || 'Unknown';
    catMap[cat] = (catMap[cat] || 0) + 1;
  });
  const catData = Object.keys(catMap).map(cat => ({ name: cat, Count: catMap[cat] })).sort((a,b) => b.Count - a.Count).slice(0, 5);

  const selectedTicket = data.find(t => t.ticket_id.toString() === selectedId);

  return (
    <div className="view-wrapper">
      <div className="page-header" style={{display: 'flex', justifyContent: 'space-between'}}>
        <div>
          <h1 className="page-title">Analytics Dashboard</h1>
          <p className="page-subtitle">Real-time overview of active ticket volumes and ML predictions.</p>
        </div>
        <button onClick={fetchData} className="nav-btn" style={{border: '1px solid #e2e8f0', height: '40px'}}>🔄 Sync</button>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-label">Global Volume</div>
          <div className="metric-value">{total}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Escalations</div>
          <div className="metric-value">{escalated}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">AI Precision</div>
          <div className="metric-value">{avgConf}%</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">High Priority</div>
          <div className="metric-value">{pMap.Critical + pMap.High}</div>
        </div>
      </div>

      <div className="charts-grid">
        <div className="chart-card">
          <div className="chart-title">Priorities Overview</div>
          <ResponsiveContainer width="100%" height="80%">
            <PieChart>
              <Pie data={priorityData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} dataKey="value" label>
                {priorityData.map((e, idx) => <Cell key={`cell-${idx}`} fill={COLORS[e.name]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-card">
          <div className="chart-title">Top Intent Classes</div>
          <ResponsiveContainer width="100%" height="80%">
            <BarChart data={catData} layout="vertical" margin={{ top: 0, right: 30, left: 20, bottom: 0 }}>
              <XAxis type="number" />
              <YAxis type="category" dataKey="name" width={100} fontSize={12} />
              <Tooltip cursor={{fill: '#f1f5f9'}} />
              <Bar dataKey="Count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Customer</th>
              <th>AI Category</th>
              <th>Conf</th>
              <th>Assigned Queue</th>
              <th>Priority</th>
            </tr>
          </thead>
          <tbody>
            {data.map(t => {
              const p = t.routing?.priority || 'medium';
              const pCap = p.charAt(0).toUpperCase() + p.slice(1);
              return (
                <tr key={t.ticket_id}>
                  <td>#{t.ticket_id}</td>
                  <td>{t.customer_name}</td>
                  <td>{t.prediction?.predicted_category}</td>
                  <td>{t.prediction?.category_confidence ? t.prediction.category_confidence.toFixed(2) : '-'}</td>
                  <td>{t.routing?.assigned_queue}</td>
                  <td><span className={`badge ${p.toLowerCase()}`}>{pCap}</span></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="drill-down card">
        <h4>Deep Dive: Model Reasoning</h4>
        <select className="drill-select" value={selectedId} onChange={e => setSelectedId(e.target.value)}>
          <option value="">Select a specific issue...</option>
          {data.map(t => <option key={t.ticket_id} value={t.ticket_id}>#{t.ticket_id} - {t.subject}</option>)}
        </select>
        {selectedTicket && (
          <div className="drill-details">
             <p><strong>Intent:</strong> {selectedTicket.prediction?.predicted_intent}</p>
             <p><strong>Execution Rule:</strong> {selectedTicket.routing?.reason}</p>
             <p style={{fontSize:'0.8rem', color:'#94a3b8', marginTop:'10px'}}>Inference latency: {selectedTicket.prediction?.inference_time_ms}ms</p>
          </div>
        )}
      </div>

    </div>
  );
}

export default App;
