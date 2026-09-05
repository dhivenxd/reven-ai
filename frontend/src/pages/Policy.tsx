import { useEffect, useState } from 'react';
import api from '../api/client';
import type { PolicyOverview } from '../types';
import './Policy.css';

const actions=[['renewal_reminder','Renewal reminder','40'],['personalized_offer','Personalized offer','40'],['discount','Discount','45'],['plan_change','Plan change','55'],['cancellation_save','Cancellation save','70']];

export function Policy(){
 const [data,setData]=useState<PolicyOverview|null>(null);
 useEffect(()=>{api.getPolicyOverview().then(setData).catch(()=>null)},[]);
 const noAction=Math.round((data?.no_action_percentage||0)*100);
 return <div className="policy-page">
  <div className="page-heading"><div><div className="page-kicker">Decision governance</div><h1 className="page-title">Policy decides when action is worth it.</h1><p className="page-description">REVEN's model can recommend an intervention, but deterministic economic and risk gates decide whether it is allowed to execute.</p></div></div>
  <section className="policy-intro"><div><span className="policy-big">{data?`${noAction}%`:'—'}</span><span className="policy-big-label">of decisions currently resolve to no action</span></div><p>That restraint is intentional. If expected incremental value does not clear the minimum economic and uplift requirements, REVEN preserves the customer's value instead of spending to intervene.</p></section>
  <section className="policy-gates"><div className="policy-section-title">Three gates before intervention</div><div className="gate-list">
   <div><b>5%</b><span>minimum uplift</span><small>The expected incremental lift must justify acting.</small></div>
   <div><b>₹5</b><span>minimum net value</span><small>Expected value after intervention costs must remain positive.</small></div>
   <div><b>30</b><span>autonomous risk ceiling</span><small>Higher-risk cases require stronger policy justification.</small></div>
  </div></section>
  <section className="thresholds"><div className="policy-section-title">Intervention thresholds</div><div className="threshold-list">
   {actions.map(([id,name,score])=><div className="threshold-row" key={id}><span>{name}</span><div className="risk-line"><i style={{width:`${Number(score)}%`}}/></div><b>{score}</b></div>)}
  </div></section>
  <section className="policy-flow"><div className="policy-section-title">How a decision moves</div><div className="flow"><span>Situation</span><i>→</i><span>Risk</span><i>→</i><span>Economics</span><i>→</i><span>Policy</span><i>→</i><strong>Decision</strong><i>→</i><span>Outcome</span></div></section>
 </div>
}
