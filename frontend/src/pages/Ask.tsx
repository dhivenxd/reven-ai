import { useState } from 'react';
import api from '../api/client';
import './Ask.css';

type Message={role:'user'|'reven';text:string};
const starters=['Why did REVEN choose no action?','Explain the last recovery decision','What is the economic reason to intervene?','Is any revenue actually recovered?'];

export function Ask(){
  const [messages,setMessages]=useState<Message[]>([]);
  const [input,setInput]=useState('');
  const [loading,setLoading]=useState(false);
  const [thinking, setThinking] = useState('');

  const send=async(value?:string)=>{
    const text=(value??input).trim();
    if(!text||loading)return;

    setMessages(m=>[...m,{role:'user',text}]);
    setInput('');
    setLoading(true);

    try {
      // Simulate a thinking state for perceived operational intelligence
      setThinking('Querying Decision Store...');
      await new Promise(r => setTimeout(r, 600));
      setThinking('Analyzing Policy Gates...');
      await new Promise(r => setTimeout(r, 600));
      setThinking('Generating Grounded Explanation...');

      const r=await api.chat(text);
      setMessages(m=>[...m,{role:'reven',text:r.message}]);
    } catch {
      setMessages(m=>[...m,{role:'reven',text:'REVEN could not reach the intelligence service. Check that the backend is running on port 8081.'}]);
    } finally {
      setLoading(false);
      setThinking('');
    }
  };

  return <div className="ask-page">
    <div className="page-heading"><div><div className="page-kicker">REVEN intelligence</div><h1 className="page-title">Ask the system that made the decision.</h1><p className="page-description">Query real decisions, recovery outcomes and policy reasoning. REVEN explains; the deterministic engine remains authoritative.</p></div></div>
    <div className="ask-workspace">
      <div className="ask-history">
        {messages.length===0?<div className="ask-empty"><div className="ask-mark">R</div><h2>What do you want to understand?</h2><div className="ask-starters">{starters.map(s=><button key={s} onClick={()=>send(s)}>{s}<span className="arrow">↗</span></button>)}</div></div>:messages.map((m,i)=><div className={`chat-line ${m.role}`} key={i}><span className="chat-label">{m.role==='reven'?'REVEN':'You'}</span><p>{m.text}</p></div>)}
        {loading&&<div className="chat-line reven"><span className="chat-label">REVEN</span><div className="thinking-state"><span className="dot"></span><span className="dot"></span><span className="dot"></span><p>{thinking || 'Analyzing...'}</p></div></div>}
      </div>
      <form className="ask-input" onSubmit={e=>{e.preventDefault();send()}}><textarea value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}} placeholder="Ask REVEN about a decision, customer, policy or outcome…" rows={1} /><button disabled={loading||!input.trim()} aria-label="Send">↑</button></form>
    </div>
  </div>
}
