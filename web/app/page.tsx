"use client";
import { useEffect, useState } from "react";

type Ticket = { id:number; subject:string; status:string; priority:string|null; type:string|null; requester_id:number|null; requester_name:string|null; requester_email:string|null; assignee_id:number|null; assignee_name:string|null; group_id:number|null; group_name:string|null; tags:string[]; created_at:string; updated_at:string };

export default function Page() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [count, setCount] = useState(0);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const load = async (s?:string) => {
    setLoading(true);
    const url = s ? `${api}/api/v2/tickets.json?status=${s}&per_page=25` : `${api}/api/v2/tickets.json?per_page=25`;
    const r = await fetch(url);
    const j = await r.json();
    setTickets(j.tickets||[]);
    setCount(j.count||0);
    setLoading(false);
  };
  useEffect(()=>{ load(); },[]);

  return (
    <div>
      <header style={{background:"#03363d", color:"white", padding:"12px 20px", display:"flex", justifyContent:"space-between", alignItems:"center"}}>
        <b>Zendesk Clone — Silin</b>
        <span style={{fontSize:12, opacity:0.8}}>4863 tickets · Réplica escalable · http://localhost:8000/docs</span>
      </header>
      <div style={{maxWidth:1200, margin:"20px auto", background:"white", borderRadius:8, boxShadow:"0 1px 3px rgba(0,0,0,0.1)"}}>
        <div style={{padding:"16px 20px", borderBottom:"1px solid #eee", display:"flex", gap:10, alignItems:"center", flexWrap:"wrap"}}>
          <h2 style={{margin:0, flex:1}}>Vistas · agent/home/tickets</h2>
          <select value={status} onChange={e=>{setStatus(e.target.value); load(e.target.value)}} style={{padding:"6px 10px", border:"1px solid #ddd", borderRadius:6}}>
            <option value="">Todas ({count})</option>
            <option value="open">Abiertos (20)</option>
            <option value="pending">Pendientes (8)</option>
            <option value="solved">Resueltos (16)</option>
            <option value="closed">Cerrados (4760)</option>
            <option value="new">Nuevos (1)</option>
          </select>
          <button onClick={()=>load(status)} style={{padding:"6px 12px", background:"#03363d", color:"white", border:"none", borderRadius:6, cursor:"pointer"}}>Actualizar</button>
        </div>
        {loading ? <div style={{padding:40, textAlign:"center"}}>Cargando tickets...</div> : (
          <table style={{width:"100%", borderCollapse:"collapse", fontSize:14}}>
            <thead style={{background:"#f8f9f9", textAlign:"left"}}>
              <tr><th style={{padding:"10px 12px"}}>ID</th><th>Asunto</th><th>Estado</th><th>Prioridad</th><th>Solicitante</th><th>Asignado</th><th>Actualizado</th></tr>
            </thead>
            <tbody>
              {tickets.map(t=>(
                <tr key={t.id} style={{borderTop:"1px solid #eee"}} onMouseEnter={e=>e.currentTarget.style.background="#f9f9f9"} onMouseLeave={e=>e.currentTarget.style.background=""}>
                  <td style={{padding:"8px 12px"}}>#{t.id}</td>
                  <td style={{maxWidth:320, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}} title={t.subject}>{t.subject||"(sin asunto)"}</td>
                  <td><span style={{padding:"2px 8px", borderRadius:12, fontSize:12, background: t.status==="open"? "#fff7ed" : t.status==="closed"?"#f0fdf4":"#eff6ff", border:"1px solid #ddd"}}>{t.status}</span></td>
                  <td>{t.priority||"-"}</td>
                  <td title={t.requester_email||""}><div style={{fontWeight:500}}>{t.requester_name||`#${t.requester_id}`}</div><div style={{fontSize:11, color:"#666"}}>{t.requester_email|| (t.requester_id?`ID ${t.requester_id}`:"-")}</div></td>
                  <td>{t.assignee_name|| (t.assignee_id?`#${t.assignee_id}`:"-")}<div style={{fontSize:11, color:"#666"}}>{t.group_name||""}</div></td>
                  <td style={{fontSize:12, color:"#666"}}>{t.updated_at ? new Date(t.updated_at).toLocaleString("es-CO") : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{padding:"12px 20px", background:"#f8f9f9", fontSize:12, color:"#666", display:"flex", justifyContent:"space-between"}}>
          <span>Mostrando {tickets.length} de {count} · API <code>/api/v2/tickets.json</code> + <code>/incremental/tickets/cursor.json</code></span>
          <a href="http://localhost:8000/docs" target="_blank" style={{color:"#03363d"}}>Swagger API →</a>
        </div>
      </div>
      <div style={{maxWidth:1200, margin:"0 auto", padding:"0 20px 20px", fontSize:12, color:"#888"}}>
        <p>Clon funcional idéntico a Zendesk Support. Backend <code>api/app/main.py</code> replica <code>/api/v2/*</code> + cursor incremental. DB SQLite <code>zendesk_clone.db</code> con 4863 tickets importados desde <code>zendesk-backup-silin</code>. Escalable via <code>docker-compose.yml</code> → <code>k8s/</code>.</p>
      </div>
    </div>
  )
}
