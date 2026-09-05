import { useEffect, useMemo, useState } from 'react';
import { BarChart, Bar, ResponsiveContainer, XAxis, Tooltip, Cell } from 'recharts';
import api from '../api/client';
import type { BenchmarkResult } from '../types';
import { useMode } from '../context/ModeContext';
import { usePolling } from '../hooks/usePolling';
import { useToast } from '../hooks/useToast';
import './Overview.css';

const labels: Record<string,string> = {
  no_action:'No action', payment_retry:'Payment retry', payment_reminder:'Payment reminder',
  renewal_reminder:'Renewal reminder', personalized_offer:'Personalized offer',
  discount:'Discount', plan_change:'Plan change', cancellation_save:'Cancellation save'
};

function money(v:number){
  const a=Math.abs(v);
  if(a>=100000) return `₹${(v/100000).toFixed(1)}L`;
  if(a>=1000) return `₹${(v/1000).toFixed(1)}K`;
  return `₹${Math.round(v).toLocaleString('en-IN')}`;
}
function pct(v:number){return `${(v*100).toFixed(1)}%`}

export function Overview(){
  const {mode}=useMode();
  const { toast, showToast } = useToast();
  const [benchmark,setBenchmark]=useState<BenchmarkResult|null>(null);
  const [review,setReview]=useState('');
  const [loading,setLoading]=useState(true);
  const [reviewLoading,setReviewLoading]=useState(false);
  const [simLoading,setSimLoading]=useState(false);

  const { data: decisionsData } = usePolling(
    () => api.getDecisions(6, 0).then(r => r.decisions),
    5000,
    mode === 'demo'
  );

  const decisions = decisionsData || [];

  useEffect(()=>{
    let active=true;
    (async()=>{
      setLoading(true);
      try{
        if(mode==='demo'){
          await api.seedDemo();
          const b=await api.getBenchmark(1000,42);
          if(!active)return;
          setBenchmark(b);
          if(!sessionStorage.getItem('reven-review-v1')) {
            setReviewLoading(true);
            try{
              const prompt = `Write ONE concise merchant-facing REVEN review (2-3 sentences, no markdown) using ONLY these verified benchmark metrics: ${JSON.stringify({
                customers:b.total_customers, intervention_rate:b.intervention_rate,
                no_action_rate:b.no_action_rate, incremental_net_revenue:b.reven.incremental_net_revenue,
                roi:b.reven.roi, intervention_cost:b.reven.intervention_cost,
                baseline_revenue:b.baseline.revenue, reven_net_revenue:b.reven.net_revenue
              })}. Explain what the numbers mean and emphasize selective intervention. Never invent causes, dates, or outcomes.`;
              const r=await api.chat(prompt);
              if(active)setReview(r.message);
              sessionStorage.setItem('reven-review-v1','1');
            }catch{ if(active)setReview('REVEN review is unavailable right now. The underlying benchmark remains available and grounded in the decision engine.'); }
            finally{if(active)setReviewLoading(false)}
          }
        } else {
          setBenchmark(null);
          setReview('Merchant mode is ready for a live integration. No live merchant data is displayed until a production connection is configured.');
        }
      } catch(e) {
        console.error(e);
      } finally {if(active)setLoading(false)}
    })();
    return ()=>{active=false};
  },[mode]);

  const handleSimulateFailure = async () => {
    setSimLoading(true);
    try {
      await api.simulatePaymentFailed();
      showToast('Simulated payment failure. REVEN is analyzing...');
    } catch (e) {
      console.error('Simulation failed:', e);
    } finally {
      setSimLoading(false);
    }
  };

  const handleSimulateCapture = async () => {
    if (decisions.length === 0) return;
    setSimLoading(true);
    try {
      const lastDecision = decisions[0];
      await api.simulatePaymentCaptured(lastDecision.decision_id);
      showToast(`Payment captured for ${lastDecision.customer_id}. Revenue recovered!`);
    } catch (e) {
      console.error('Simulation failed:', e);
    } finally {
      setSimLoading(false);
    }
  };

  const mix=useMemo(()=>benchmark?Object.entries(benchmark.intervention_breakdown)
    .map(([type,s])=>({type,label:labels[type]||type,value:s.decisions}))
    .sort((a,b)=>b.value-a.value):[],[benchmark]);

  const recent=decisions.slice(0,4);

  if(mode==='merchant') return (
    <div className="overview">
      <div className="page-heading">
        <div><div className="page-kicker">Merchant workspace</div><h1 className="page-title">Live revenue intelligence.</h1><p className="page-description">The same REVEN engine is ready to evaluate merchant events. Live production data stays hidden until the integration is connected.</p></div>
        <div className="live-state"><span/>Integration not connected</div>
      </div>
      <section className="merchant-empty">
        <div className="empty-mark">R</div>
        <div><h2>Connect the merchant feed</h2><p>Once Razorpay production webhooks are connected, REVEN will use this same workspace for real customer decisions and confirmed recovery outcomes.</p></div>
      </section>
    </div>
  );

  return (
    <div className="overview">
      {toast && <div className="toast-notification">{toast}</div>}
      <div className="page-heading overview-heading">
        <div><div className="page-kicker">Demo workspace · 1,000 simulated customers</div><h1 className="page-title">Revenue decisions, not payment retries.</h1><p className="page-description">REVEN evaluates risk and economics before it spends an intervention. The result is a recovery system that knows when to act — and when not to.</p></div>
      </div>

      <section className="simulator-panel">
        <div className="sim-header">
          <div className="sim-title">Recovery Simulator</div>
          <div className="sim-desc">Trigger the recovery state machine to see real-time propagation from Backend → API → Frontend.</div>
        </div>
        <div className="sim-actions">
          <div className="sim-group">
            <span className="sim-label">Phase 1: Failure</span>
            <button className="sim-btn" onClick={handleSimulateFailure} disabled={simLoading}>
              {simLoading ? 'Analyzing...' : 'Simulate Payment Failure'}
            </button>
            <span className="sim-hint">Triggers `payment.failed` → REVEN Analysis → Decision</span>
          </div>
          <div className="sim-group">
            <span className="sim-label">Phase 2: Recovery</span>
            <button className="sim-btn" onClick={handleSimulateCapture} disabled={simLoading || decisions.length === 0}>
              {simLoading ? 'Capturing...' : 'Simulate Payment Capture'}
            </button>
            <span className="sim-hint">Triggers `payment.captured` → Revenue Recovery</span>
          </div>
          <div className="sim-group">
            <span className="sim-label">Data</span>
            <button className="sim-btn ghost" onClick={()=>{sessionStorage.removeItem('reven-review-v1');window.location.reload()}}>Refresh Dataset</button>
          </div>
        </div>
      </section>

      <section className="overview-hero">
        <div className="hero-card">
          <div className="hero-card-header"><span className="hero-card-label">Incremental Net Revenue</span></div>
          <div className="hero-card-value">{loading?<div className="hero-number skeleton"/>:money(benchmark?.reven.incremental_net_revenue||0)}</div>
          <div className="hero-card-meta">vs. legacy recovery policy</div>
        </div>
        <div className="hero-card">
          <div className="hero-card-header"><span className="hero-card-label">Return on Intervention</span></div>
          <div className="hero-card-value">{benchmark?benchmark.reven.roi.toFixed(2):'—'}x</div>
          <div className="hero-card-meta">ROI efficiency</div>
        </div>
        <div className="hero-card">
          <div className="hero-card-header"><span className="hero-card-label">Intervention Rate</span></div>
          <div className="hero-card-value">{benchmark?pct(benchmark.intervention_rate):'—'}</div>
          <div className="hero-card-meta">Customers intervened on</div>
        </div>
        <div className="hero-card">
          <div className="hero-card-header"><span className="hero-card-label">No-Action Rate</span></div>
          <div className="hero-card-value">{benchmark?pct(benchmark.no_action_rate):'—'}</div>
          <div className="hero-card-meta">Decisions deliberately withheld</div>
        </div>
      </section>

      <section className="review-banner">
        <div className="review-text">
          {reviewLoading?<div className="review-loading">Reading the current decision set…</div>:<p>{review||'REVEN is reviewing the current decision set.'}</p>}
        </div>
        <div className="review-badge">Grounded AI Review</div>
      </section>

      <section className="analytics-grid">
        <div className="analytics-card">
          <div className="section-title">Economics at a Glance</div>
          <div className="chart-container">
            {loading?<div className="chart-loading skeleton"/>:
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={[
                  {name:'Legacy',value:benchmark?.baseline.revenue||0},
                  {name:'REVEN',value:benchmark?.reven.net_revenue||0},
                ]} margin={{top:20,right:8,left:0,bottom:4}}>
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill:'#6d6d66',fontSize:12}}/>
                  <Tooltip formatter={(value)=>money(Number(value))} cursor={{fill:'rgba(31,31,31,.035)'}}/>
                  <Bar dataKey="value" radius={[3,3,0,0]} barSize={72}>
                    <Cell fill="#c9c9c2"/><Cell fill="#1f1f1f"/>
                  </Bar>
                </BarChart>
              </ResponsiveContainer>}
          </div>
          <div className="metric-line" style={{marginTop:'20px', display:'flex', justifyContent:'space-between', fontSize:'12px', color:'var(--muted)'}}>
            <span>REVEN net revenue: <b>{money(benchmark?.reven.net_revenue||0)}</b></span>
            <span>Intervention cost: <b>{money(benchmark?.reven.intervention_cost||0)}</b></span>
          </div>
        </div>

        <div className="analytics-card">
          <div className="section-title">Decision Mix</div>
          <div className="mix-list">
            {mix.slice(0,5).map((item,i)=><div className="mix-item" key={item.type}>
              <div className="mix-row"><span className="mix-label">{item.label}</span><span className="mix-value">{item.value}</span></div>
              <div className="mix-bar-bg"><i className="mix-bar-fill" style={{width:`${Math.max(3,(item.value/(benchmark?.total_decisions||1))*100)}%`,background:i===0?'#1f1f1f':'#a8a8a1'}}/></div>
            </div>)}
          </div>
        </div>
      </section>

      <section className="recent-section">
        <div className="section-head"><div><h2 className="section-title">Recent Decisions</h2><p className="page-description">The latest evaluations from the demo workspace.</p></div><a href="/decisions" style={{fontSize:'12px', fontWeight:600, color:'var(--ink', textDecoration:'underline'}}>View all</a></div>
        <div className="recent-table-wrap">
          <div className="table-header">
            <span>Customer</span><span>Decision</span><span>Reason</span><span>Value</span><span>Status</span>
          </div>
          <div className="decision-list">
            {recent.map(d=><div className="table-row" key={d.decision_id} onClick={()=>{window.location.href=`/decisions`}}>
              <div className="customer-cell"><div className="customer-avatar">{d.customer_id.slice(-1).toUpperCase()}</div><div><b style={{fontSize:'13px', display:'block'}}>{d.customer_id}</b><small style={{fontSize:'10px', color:'var(--muted)'}}>{new Date(d.created_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</small></div></div>
              <div className="decision-type" style={{fontWeight:600}}>{labels[d.intervention_type]||d.intervention_type}</div>
              <div className="decision-reason" style={{color:'var(--muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{d.reason}</div>
              <div className="decision-value" style={{fontWeight:600, textAlign:'right'}}>{d.intervention_type==='no_action'?'—':money(d.expected_net_revenue)}</div>
              <div className={`status-pill status-${d.execution_status}`}>{d.execution_status}</div>
            </div>)}
          </div>
        </div>
      </section>
    </div>
  );
}
