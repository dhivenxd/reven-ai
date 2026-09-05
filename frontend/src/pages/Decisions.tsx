import { useMemo, useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { DecisionPath } from '../components/DecisionPath';
import api from '../api/client';
import type { Decision } from '../types';
import './Decisions.css';

const labels:Record<string,string>={no_action:'No action',payment_retry:'Payment retry',payment_reminder:'Payment reminder',renewal_reminder:'Renewal reminder',personalized_offer:'Personalized offer',discount:'Discount',plan_change:'Plan change',cancellation_save:'Cancellation save'};
const money=(v:number)=>v>=1000?`₹${(v/1000).toFixed(1)}K`:`₹${Math.round(v).toLocaleString('en-IN')}`;

function Detail({d,onClose}:{d:Decision;onClose:()=>void}){
 return <div className="detail-backdrop" onClick={onClose}><aside className="detail-panel" onClick={e=>e.stopPropagation()}>
  <button className="detail-close" onClick={onClose} aria-label="Close decision detail">×</button>
  <div className="detail-kicker">{d.decision_id}</div>
  <h2 style={{marginBottom:'24px'}}>{d.customer_id}</h2>

  <div className="detail-decision" style={{marginBottom:'32px'}}>
    <span>{labels[d.intervention_type]}</span>
    <b style={{fontSize:'24px', marginLeft:'12px'}}>{d.intervention_type==='no_action'?'Withheld':money(d.expected_net_revenue)}</b>
  </div>

  <DecisionPath decision={d} loading={false} />

  {d.razorpay_payment_link_id && (
    <div className="payment-link-action" style={{marginTop:'24px', padding:'16px', background:'var(--paper)', borderRadius:'var(--radius-md)', border:'1px solid var(--line)', display:'flex', justifyContent:'space-between', alignItems:'center'}}>
      <div>
        <div style={{fontSize:'11px', fontWeight:600, color:'var(--ink)'}}>Payment Link Available</div>
        <div style={{fontSize:'10px', color:'var(--muted)'}}>Customer can complete payment via Razorpay Sandbox</div>
      </div>
      <a href={d.razorpay_payment_link_id} target="_blank" rel="noopener noreferrer" className="payment-link-btn" style={{background:'var(--ink)', color:'#fff', padding:'8px 12px', borderRadius:'var(--radius-sm)', fontSize:'11px', fontWeight:600, textDecoration:'none'}}>
        Open Link
      </a>
    </div>
  )}

  {d.alternatives?.length>0&&<div className="alternatives" style={{marginTop:'32px'}}><span className="alternatives-label">Evaluated alternatives</span>{d.alternatives.slice(0,4).map((a,i)=><div key={i} className="alternative-item"><b>{labels[a.intervention_type]||a.intervention_type}</b><em>{money(a.expected_net_revenue)}</em></div>)}</div>}
  </aside></div>
}

export function Decisions(){
  const { data: items = [], loading } = usePolling(() => api.getDecisions(50, 0).then(r => r.decisions));
  const [selected,setSelected]=useState<Decision|null>(null); const [filter,setFilter]=useState('all');

  const filtered=useMemo(()=> {
    const safeItems = items || [];
    return safeItems.length === 0 ? [] : (filter==='all' ? safeItems : safeItems.filter(d=>d.intervention_type===filter));
  },[items,filter]);
  return <div className="decisions-page">
    <div className="page-heading"><div><div className="page-kicker">Decision intelligence</div><h1 className="page-title">See why REVEN chose.</h1><p className="page-description">A focused view of recent decisions. Select one to follow the reasoning from situation to outcome.</p></div></div>
    <div className="decision-controls"><div className="decision-tabs">{[['all','All'],['payment_retry','Retry'],['renewal_reminder','Renewal'],['personalized_offer','Offer'],['no_action','No action']].map(([v,l])=><button key={v} className={filter===v?'active':''} onClick={()=>setFilter(v)}>{l}</button>)}</div><span>{(filtered || []).length} shown</span></div>
    <div className="decision-summary"><b>{(items || []).length}</b><span>evaluated</span><i/><b>{(items || []).filter(d=>d.intervention_type==='no_action').length}</b><span>no action</span><i/><b>{(items || []).filter(d=>d.execution_status==='captured').length}</b><span>captured</span></div>
    <div className="decision-table-head"><span>Customer</span><span>Decision</span><span>Reason</span><span>Value</span><span>Status</span></div>
    <div className="decision-list">
     {loading?<div className="decision-empty">Loading decisions…</div>:(filtered || []).length===0?<div className="decision-empty">No decisions match this filter.</div>:(filtered || []).map(d=><button className="decision-line" key={d.decision_id} onClick={()=>setSelected(d)}>
      <span className="customer">{d.customer_id}<small>{new Date(d.created_at).toLocaleDateString('en-IN')}</small></span>
      <span className="type">{labels[d.intervention_type]}</span>
      <span className="reason">{d.reason}</span>
      <span className="value">{d.intervention_type==='no_action'?'—':money(d.expected_net_revenue)}</span>
      <span className={`state ${d.execution_status}`}>{d.execution_status}</span>
     </button>)}
    </div>
    {selected&&<Detail d={selected} onClose={()=>setSelected(null)}/>}
  </div>
}
