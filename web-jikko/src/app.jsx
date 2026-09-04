import { useEffect, useState } from 'react'
import { Icon } from './icons.jsx'

const API = 'http://localhost:8000'

export default function App(){
  const [tickets, setTickets]=useState([])
  const [count, setCount]=useState(0)
  const [q, setQ]=useState('')
  const [status, setStatus]=useState('')
  const [selected, setSelected]=useState(null)
  const [comments, setComments]=useState([])
  const [audits, setAudits]=useState([])
  const [loading, setLoading]=useState(true)
  const [editing, setEditing]=useState(null)
  const [editVals, setEditVals]=useState({})
  const [groups, setGroups]=useState([])
  const [saving, setSaving]=useState(false)
  const [replyBody, setReplyBody]=useState('')
  const [toEmails, setToEmails]=useState('')
  const [ccEmails, setCcEmails]=useState('')
  const [sending, setSending]=useState(false)
  const [ticketFields, setTicketFields]=useState([])
  const [customVals, setCustomVals]=useState({})

  const load = async (s=q, query='')=>{
    setLoading(true)
    let url=`${API}/api/v2/tickets.json?per_page=25`
    if(s) url+=`&status=${s}`
    // busqueda simple: si hay query, usa search
    if(query){
      const r=await fetch(`${API}/api/v2/search.json?query=${encodeURIComponent(query)}`)
      if(r.ok){ const j=await r.json(); setTickets(j.results||[]); setCount(j.count||0); setLoading(false); return }
    }
    const r=await fetch(url)
    const j=await r.json()
    setTickets(j.tickets||[])
    setCount(j.count||0)
    setLoading(false)
  }
  useEffect(()=>{ load(); fetch(`${API}/api/v2/groups.json`).then(r=>r.json()).then(j=>setGroups(j.groups||[])).catch(()=>{}); fetch(`${API}/api/v2/ticket_fields.json`).then(r=>r.json()).then(j=>setTicketFields(j.ticket_fields||[])).catch(()=>{}) },[])

  const openTicket = async (t)=>{
    setSelected(t)
    setEditing(null)
    setEditVals({subject: t.subject, status: t.status, priority: t.priority||'normal', group_id: t.group_id||'', tags: (t.tags||[]).join(', ')})
    // cargar custom_fields a estado para 10 dropdowns
    const cfMap={}
    ;(t.custom_fields||[]).forEach(cf=>{ cfMap[cf.id]=cf.value })
    setCustomVals(cfMap)
    setReplyBody('')
    setToEmails(t.requester_email||'')
    setCcEmails('')
    const [c,a] = await Promise.all([
      fetch(`${API}/api/v2/tickets/${t.id}/comments.json`).then(r=>r.json()).catch(()=>({comments:[]})),
      fetch(`${API}/api/v2/tickets/${t.id}/audits.json`).then(r=>r.json()).catch(()=>({audits:[]}))
    ])
    setComments(c.comments||[])
    setAudits(a.audits||[])
  }

  const sendReply = async (isPublic)=>{
    if(!selected || !replyBody.trim()){ alert('Escribe un mensaje'); return }
    setSending(true)
    try{
      const payload={comment:{body: replyBody, public: isPublic, to_emails: toEmails.split(',').map(s=>s.trim()).filter(Boolean), cc_emails: ccEmails.split(',').map(s=>s.trim()).filter(Boolean)}}
      const r=await fetch(`${API}/api/v2/tickets/${selected.id}/comments.json`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
      if(r.ok){
        const j=await r.json()
        setComments(prev=>[...prev, j.comment])
        setReplyBody('')
        // actualizar updated_at en ticket
        const t=await fetch(`${API}/api/v2/tickets/${selected.id}.json`).then(r=>r.json()).then(j=>j.ticket).catch(()=>null)
        if(t) setSelected(t)
      } else {
        const txt=await r.text(); alert('Error '+r.status+': '+txt)
      }
    } catch(e){ alert('Error '+e) }
    setSending(false)
  }

  const fieldIds = [41302403884557,11622270573837,35139407697805,12491763418637,11588515928205,11588303168525,38276732136461,30920328139405,11749979171469,11393617430669,30598614640397]
  const getField = (id)=> ticketFields.find(f=>f.id===id)
  const getOptions = (id)=> {
    const f=getField(id)
    if(!f) return []
    return f.custom_field_options|| f.system_field_options || []
  }
  // dependencias Entidad->Tributo etc: filtrar por co-ocurrencia simple (si Entidad seleccionada, filtrar Tributo a los que co-ocurren en historial - por ahora muestra todos)
  const isNoTarjeta = (id)=> id===30598614640397

  const saveClassification = async ()=>{
    if(!selected) return
    setSaving(true)
    const payload = {
      ticket: {
        subject: editVals.subject,
        status: editVals.status,
        priority: editVals.priority,
        group_id: editVals.group_id ? parseInt(editVals.group_id) : null,
        tags: editVals.tags ? editVals.tags.split(',').map(s=>s.trim()).filter(Boolean) : []
      }
    }
    try{
      const r=await fetch(`${API}/api/v2/tickets/${selected.id}.json`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
      if(r.ok){
        const j=await r.json()
        const updated=j.ticket
        setSelected(updated)
        setTickets(prev=>prev.map(x=>x.id===updated.id? updated: x))
        setEditing(null)
        // refrescar audits
        const a=await fetch(`${API}/api/v2/tickets/${updated.id}/audits.json`).then(r=>r.json()).catch(()=>({audits:[]}))
        setAudits(a.audits||[])
      } else {
        alert('Error al guardar: '+r.status)
      }
    } catch(e){ alert('Error '+e) }
    setSaving(false)
  }

  return (
    <div style={{display:'flex', height:'100vh', overflow:'hidden'}}>
      {/* Sidebar Jikkoops */}
      <aside className="sidebar" style={{width:260, background:'var(--surface)', borderRight:'1px solid var(--line-1)', display:'flex', flexDirection:'column'}}>
        <div style={{height:52, display:'flex', alignItems:'center', padding:'0 16px', borderBottom:'1px solid var(--line-1)', gap:8}}>
          <div style={{width:28,height:28, background:'var(--accent)', color:'#fff', display:'grid', placeItems:'center', borderRadius:6, fontWeight:700}}>Z</div>
          <b>Jikkodesk Support</b><span style={{fontSize:11, opacity:.6}}>silin</span>
        </div>
        <nav style={{padding:12, flex:1, overflow:'auto'}}>
          <div className="mono" style={{fontSize:10, opacity:.6, margin:'8px 0 6px'}}>VISTAS</div>
          {[
            ['Todos','',4863],
            ['Nuevos','new',1],
            ['Abiertos','open',20],
            ['Pendientes','pending',8],
            ['Resueltos','solved',16],
            ['Cerrados','closed',4760],
          ].map(([label,val,cnt])=>(
            <div key={label} onClick={()=>{setStatus(val); load(val)}} className="nav-item" style={{padding:'7px 10px', borderRadius:6, cursor:'pointer', background: status===val ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : 'transparent', display:'flex', justifyContent:'space-between'}}>
              <span>{label}</span><span className="mono" style={{fontSize:11, background:'var(--line-2)', padding:'1px 6px', borderRadius:4}}>{cnt}</span>
            </div>
          ))}
          <div className="mono" style={{fontSize:10, opacity:.6, margin:'16px 0 6px'}}>EQUIPOS</div>
          <div style={{display:'flex', gap:6, flexWrap:'wrap'}}>
            {['Soporte-GZ','TRI','DEV','DBA','PO'].map(e=>(<span key={e} className="tag" style={{background:'color-mix(in srgb, var(--accent) 14%, transparent)', border:'1px solid var(--line-1)'}}>{e}</span>))}
          </div>
        </nav>
        <div style={{padding:12, borderTop:'1px solid var(--line-1)', fontSize:12, display:'flex', alignItems:'center', gap:8}}>
          <div style={{width:22,height:22, borderRadius:'50%', background:'var(--copper)', display:'grid', placeItems:'center', color:'#fff', fontSize:11}}>NC</div> Nicolas Chala
        </div>
      </aside>

      <main style={{flex:1, display:'flex', flexDirection:'column', overflow:'hidden', background:'var(--bg)'}}>
        {/* Topbar */}
        <div style={{height:52, display:'flex', alignItems:'center', padding:'0 16px', gap:12, borderBottom:'1px solid var(--line-1)', background:'var(--surface)'}}>
          <span className="mono" style={{fontSize:11, opacity:.6}}>JikkoOps / Soporte / Tickets</span>
          <div style={{flex:1}}/>
          <div className="shell__search" style={{display:'flex', alignItems:'center', gap:6, background:'var(--line-2)', padding:'6px 10px', borderRadius:6}}>
            <Icon name="search" size={14}/><input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter' && load(status, q)} placeholder="Buscar por asunto, solicitante o ID..." style={{border:'none', background:'transparent', outline:'none', width:260}}/>
          </div>
          <button className="btn" onClick={()=>load(status,q)}><Icon name="search" size={14}/> Filtrar</button>
          <span className="badge-dot" style={{width:8,height:8, background:'var(--success)', borderRadius:'50%', display:'inline-block'}}/> <span style={{fontSize:12}}>API Conectada</span>
        </div>

        {/* KPI Bar */}
        <div style={{display:'flex', gap:8, padding:'10px 16px', background:'var(--bg-1)', borderBottom:'1px solid var(--line-1)', overflowX:'auto'}}>
          {[
            ['Nuevos',1,'#0A60C2'],
            ['Abiertos',20,'#DC2626'],
            ['Pendientes',8,'#B8946A'],
            ['Resueltos hoy',16,'#17A34A'],
            ['Total',count,'var(--ink-1)'],
          ].map(([label,val,color])=>(
            <div key={label} className="card" style={{minWidth:140, padding:'10px 14px', background:'var(--surface)', border:'1px solid var(--line-1)', borderRadius:12}}>
              <div className="mono" style={{fontSize:10, color:'var(--ink-3)', textTransform:'uppercase'}}>{label}</div>
              <div style={{fontSize:24, fontWeight:700, color, fontVariantNumeric:'tabular-nums'}}>{val}</div>
            </div>
          ))}
          <div style={{marginLeft:'auto', fontSize:11, color:'var(--ink-3)', alignSelf:'center'}}>4863 tickets • 4805 hilos • 12.3 GB adjuntos (absoluto)</div>
        </div>

        {/* Soporte layout */}
        <div className="soporte-layout" style={{display:'flex', flex:1, overflow:'hidden'}}>
          <div style={{flex:1, display:'flex', flexDirection:'column', overflow:'hidden', background:'var(--surface)', margin:12, border:'1px solid var(--line-1)', borderRadius:12, boxShadow:'var(--shadow-sm)'}}>
            <div style={{padding:'12px 16px', borderBottom:'1px solid var(--line-1)', display:'flex', alignItems:'center', gap:10}}>
              <b>Tickets</b> <span className="mono" style={{fontSize:11, background:'var(--line-2)', padding:'2px 6px', borderRadius:4}}>{count} resultados</span>
              <select value={status} onChange={e=>{setStatus(e.target.value); load(e.target.value)}} className="input" style={{marginLeft:'auto', height:32}}><option value="">Todas</option><option value="open">Abiertos</option><option value="pending">Pendientes</option><option value="solved">Resueltos</option><option value="closed">Cerrados</option><option value="new">Nuevos</option></select>
            </div>
            <div className="table-wrap" style={{flex:1, overflow:'auto'}}>
              {loading ? <div style={{padding:40, textAlign:'center'}}>Cargando 4863 tickets...</div> : (
                <table className="table" style={{width:'100%', minWidth:1320}}>
                  <thead style={{position:'sticky', top:0, background:'var(--bg-2)', zIndex:1}}>
                    <tr className="mono" style={{fontSize:9, textTransform:'uppercase', color:'var(--ink-3)'}}><th style={{padding:'8px 12px'}}><input type="checkbox"/></th><th>ID</th><th>Asunto</th><th>Solicitante</th><th>Asignado</th><th>Grupo</th><th>Estado</th><th>Prioridad</th><th>Actualizado</th></tr>
                  </thead>
                  <tbody>
                    {tickets.map(t=>(
                      <tr key={t.id} onClick={()=>openTicket(t)} style={{cursor:'pointer', borderTop:'1px solid var(--line-1)'}}>
                        <td style={{padding:'8px 12px'}}><input type="checkbox" onClick={e=>e.stopPropagation()}/></td>
                        <td className="mono" style={{color:'var(--accent)', fontWeight:600}}>#{t.id}</td>
                        <td style={{maxWidth:380, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}} title={t.subject}>{t.subject||'(sin asunto)'}</td>
                        <td><div style={{fontWeight:500}}>{t.requester_name||'#'+t.requester_id}</div><div className="mono" style={{fontSize:11, color:'var(--ink-3)'}}>{t.requester_email||''}</div></td>
                        <td>{t.assignee_name|| (t.assignee_id?'#'+t.assignee_id:'-')}</td>
                        <td><span className="tag" style={{background:'color-mix(in srgb, var(--accent) 14%, transparent)'}}>{t.group_name|| t.group_id || '-'}</span></td>
                        <td><span className="badge-dot" style={{display:'inline-flex', alignItems:'center', gap:6, border:'1px solid var(--line-1)', padding:'2px 8px', borderRadius:12}}><span style={{width:6,height:6, borderRadius:'50%', background: t.status==='open'?'#DC2626':t.status==='pending'?'#B8946A':t.status==='closed'?'#17A34A':'#0A60C2', display:'inline-block'}}/>{t.status}</span></td>
                        <td>{t.priority||'-'}</td>
                        <td className="mono" style={{fontSize:11, color:'var(--ink-3)'}}>{t.updated_at? new Date(t.updated_at).toLocaleDateString('es-CO'): '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Modal */}
      {selected && (
        <div className="modal-overlay" onClick={()=>setSelected(null)} style={{position:'fixed', inset:0, background:'rgba(0,0,0,.42)', display:'grid', placeItems:'center', zIndex:50}}>
          <div className="modal modal--wide" onClick={e=>e.stopPropagation()} style={{width:'min(1240px,96vw)', height:'92vh', background:'var(--surface)', borderRadius:12, overflow:'hidden', display:'flex', flexDirection:'column', boxShadow:'var(--shadow-md)'}}>
            <div style={{padding:'14px 16px', borderBottom:'1px solid var(--line-1)', display:'flex', alignItems:'center', gap:10, flexShrink:0}}>
              <span className="mono" style={{fontWeight:700}}>#{selected.id}</span> <span style={{fontSize:12, color:'var(--ink-3)'}}>{selected.requester_name} • {selected.requester_email}</span>
              <select value={selected.status} onChange={()=>{}} className="input" style={{marginLeft:'auto', height:32}}><option>open</option><option>pending</option><option>solved</option><option>closed</option></select>
              <button className="btn btn--icon" onClick={()=>setSelected(null)}><Icon name="x"/></button>
            </div>
            <div style={{padding:'12px 16px', borderBottom:'1px solid var(--line-1)', flexShrink:0, background:'var(--bg-1)'}}>
              <div style={{display:'flex', alignItems:'center', gap:8}}>
                {editing==='classification' ? (
                  <input value={editVals.subject} onChange={e=>setEditVals({...editVals, subject:e.target.value})} className="input" style={{flex:1, fontSize:14, fontWeight:600}} placeholder="Asunto"/>
                ) : (
                  <div style={{fontSize:14, fontWeight:600, flex:1, display:'flex', alignItems:'center', gap:8}}>{selected.subject} <button className="btn btn--icon" onClick={()=>setEditing('classification')} title="Editar clasificación" style={{marginLeft:4}}><Icon name="pencil" size={12}/></button></div>
                )}
                {editing==='classification' && <button className="btn btn--icon" onClick={()=>setEditing(null)}><Icon name="x" size={12}/></button>}
              </div>
              {editing==='classification' ? (
                <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginTop:8}}>
                  <input value={editVals.subject} onChange={e=>setEditVals({...editVals, subject:e.target.value})} className="input" placeholder="Asunto" style={{gridColumn:'1 / span 2'}}/>
                  <select value={editVals.status} onChange={e=>setEditVals({...editVals, status:e.target.value})} className="input"><option value="new">new</option><option value="open">open</option><option value="pending">pending</option><option value="solved">solved</option><option value="closed">closed</option></select>
                  <select value={editVals.priority} onChange={e=>setEditVals({...editVals, priority:e.target.value})} className="input"><option value="low">low</option><option value="normal">normal</option><option value="high">high</option><option value="urgent">urgent</option></select>
                  <select value={editVals.group_id} onChange={e=>setEditVals({...editVals, group_id:e.target.value})} className="input"><option value="">Sin grupo</option>{groups.map(g=>(<option key={g.id} value={g.id}>{g.name}</option>))}</select>
                  <input value={editVals.tags} onChange={e=>setEditVals({...editVals, tags:e.target.value})} className="input" placeholder="tags, separados por coma" style={{gridColumn:'1 / span 2'}}/>
                  {/* 10 dropdowns clasificación + No-Tarjeta */}
                  {fieldIds.map(fid=>{
                    const f=getField(fid)
                    if(!f) return null
                    const opts=getOptions(fid)
                    const isText=isNoTarjeta(fid)
                    return (
                      <div key={fid} style={{display:'flex', flexDirection:'column', gap:4}}>
                        <span className="mono" style={{fontSize:10, color:'var(--ink-3)', textTransform:'uppercase'}}>{f.title}</span>
                        {isText ? (
                          <input value={customVals[fid]||''} onChange={e=>setCustomVals({...customVals, [fid]: e.target.value})} className="input" placeholder={f.title}/>
                        ) : (
                          <select value={customVals[fid]||''} onChange={e=>setCustomVals({...customVals, [fid]: e.target.value})} className="input">
                            <option value="">— {f.title} —</option>
                            {opts.map(opt=>(<option key={opt.value} value={opt.value}>{opt.name}</option>))}
                          </select>
                        )}
                      </div>
                    )
                  })}
                  <div style={{gridColumn:'1 / span 2', display:'flex', gap:6, justifyContent:'flex-end', marginTop:4}}>
                    <button className="btn" onClick={()=>setEditing(null)}>Cancelar</button>
                    <button className="btn btn--primary" onClick={async ()=>{
                      // guardar custom_fields 10 dropdowns
                      const cfs=Object.entries(customVals).filter(([k,v])=>v!=='' && v!=null).map(([k,v])=>({id: parseInt(k), value: v}))
                      const payload={ticket:{subject: editVals.subject, status: editVals.status, priority: editVals.priority, group_id: editVals.group_id? parseInt(editVals.group_id):null, tags: editVals.tags? editVals.tags.split(',').map(s=>s.trim()).filter(Boolean):[], custom_fields: cfs}}
                      setSaving(true)
                      try{
                        const r=await fetch(`${API}/api/v2/tickets/${selected.id}.json`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
                        if(r.ok){ const j=await r.json(); setSelected(j.ticket); setTickets(prev=>prev.map(x=>x.id===j.ticket.id? j.ticket: x)); setEditing(null); const a=await fetch(`${API}/api/v2/tickets/${j.ticket.id}/audits.json`).then(r=>r.json()).catch(()=>({audits:[]})); setAudits(a.audits||[]) } else alert('Error '+r.status)
                      }catch(e){ alert(e)} setSaving(false)
                    }} disabled={saving}>{saving?'Guardando...':'Guardar'}</button>
                  </div>
                </div>
              ) : (
                <div className="mono" style={{fontSize:11, color:'var(--ink-3)', marginTop:4, display:'flex', alignItems:'center', gap:6, flexWrap:'wrap'}}>
                  <span>{selected.tags?.join(' • ') || 'sin tags'}</span><span>•</span><span>{selected.group_name|| selected.group_id || 'sin grupo'}</span><span>•</span><span>{selected.priority||'-'}</span><span>•</span><span>{(selected.custom_fields_enriched||[]).slice(0,3).map(cf=>`${cf.title}: ${cf.value_name||cf.value||''}`).join(' • ')}</span><span>•</span><span>{selected.updated_at? new Date(selected.updated_at).toLocaleString('es-CO'):''}</span>
                  <span style={{marginLeft:'auto', display:'flex', alignItems:'center', gap:4}}><Icon name="pencil" size={12}/> Clasificación (10+No-Tarjeta)</span>
                </div>
              )}
            </div>
            <div style={{display:'flex', flex:1, overflow:'hidden', minHeight:0}}>
              <div style={{flex:1, minWidth:320, padding:16, borderRight:'1px solid var(--line-1)', overflow:'auto'}}>
                <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, fontSize:12}}>
                  <div><b>Solicitante</b><br/>{selected.requester_name}<br/><span className="mono" style={{fontSize:11}}>{selected.requester_email}</span></div>
                  <div><b>Asignado</b><br/>{selected.assignee_name||'-'}<br/><span className="mono" style={{fontSize:11}}>{selected.group_name||''}</span></div>
                </div>
                {/* Solicitud del cliente - descripción completa */}
                <div style={{marginTop:12, padding:12, background:'var(--bg-1)', border:'1px solid var(--line-1)', borderRadius:8}}>
                  <div style={{fontSize:11, fontWeight:700, color:'var(--ink-3)', textTransform:'uppercase', marginBottom:6, display:'flex', alignItems:'center', gap:6}}><Icon name="fileText" size={12}/> Solicitud del cliente</div>
                  <div style={{fontSize:13, whiteSpace:'pre-wrap', lineHeight:1.5}}>{selected.raw?.description || selected.description || selected.raw_subject || selected.subject || '(sin descripción)'}</div>
                  {selected.raw?.via && <div className="mono" style={{fontSize:11, color:'var(--ink-3)', marginTop:6}}>Canal: {selected.raw.via.channel} • Creado: {selected.created_at? new Date(selected.created_at).toLocaleString('es-CO'):''}</div>}
                </div>

                <h4 style={{margin:'16px 0 8px'}}>Conversación — {comments.length} hilos (trazabilidad)</h4>
                <div style={{display:'flex', flexDirection:'column', gap:10}}>
                  {comments.map((c,i)=>{
                    // helper para detectar imagen
                    const isImage = (fname, ctype) => ctype?.startsWith('image/') || /\.(png|jpg|jpeg|gif|bmp|webp)$/i.test(fname||'')
                    // reemplazar inline token por local si existe
                    let html = c.html_body || c.body || ''
                    // preview de adjuntos como imagen inline estilo Zendesk
                    return (
                    <div key={c.id||i} style={{display:'flex', gap:8, background: c.public? '#F5F0EB':'#F0F4FF', padding:10, borderRadius:8, border:'1px solid var(--line-1)'}}>
                      <div style={{width:22,height:22, borderRadius:'50%', background: c.public? 'var(--copper)':'var(--accent)', color:'#fff', display:'grid', placeItems:'center', fontSize:10, flex:'0 0 22px'}}>{c.public? 'C':'A'}</div>
                      <div style={{flex:1, overflow:'hidden'}}>
                        <div className="mono" style={{fontSize:11, color:'var(--ink-3)'}}>{new Date(c.created_at).toLocaleString('es-CO')} • {c.public?'Público':'Nota interna'} • {c.attachments?.length? `${c.attachments.length} adjuntos`:''} • {c.author_name ? `${c.author_name} ${c.author_email? `<${c.author_email}>`:''} ${c.author_role? `(${c.author_role})`:''}` : `#${c.author_id}`}</div>
                        <div style={{fontSize:13, marginTop:6, lineHeight:1.5, wordBreak:'break-word'}} dangerouslySetInnerHTML={{__html: html}}/>
                        {/* Adjuntos como en Zendesk: imagen inline + file preview */}
                        {c.attachments?.length>0 && (
                          <div style={{marginTop:8, display:'flex', flexDirection:'column', gap:8}}>
                            {c.attachments.map(att=>{
                              const img = isImage(att.file_name, att.content_type)
                              const attId = att.id && String(att.id) !== 'undefined' ? att.id : ''
                              const sanitized = att.file_name.replace(/[<>:"/\\|?*]/g,'_')
                              const localUrl = attId ? `${API}/attachments/${selected.id}/${attId}_${sanitized}` : `${API}/attachments/${selected.id}/${sanitized}`
                              // fallback a content_url si local no existe (para 4 fails con :)
                              return (
                                <div key={att.id} style={{border:'1px solid var(--line-1)', borderRadius:8, overflow:'hidden', background:'var(--surface)'}}>
                                  {img ? (
                                    <div>
                                      <img src={att.content_url} onError={e=>e.currentTarget.src=localUrl} alt={att.file_name} style={{maxWidth:'100%', maxHeight:360, display:'block', objectFit:'contain', background:'var(--bg-2)'}}/>
                                      <div style={{padding:'6px 8px', display:'flex', alignItems:'center', gap:6, fontSize:12, borderTop:'1px solid var(--line-1)'}}><Icon name="fileText" size={12}/> {att.file_name} <span className="mono" style={{fontSize:11, color:'var(--ink-3)'}}>{(att.size/1024).toFixed(1)} KB • {att.content_type}</span> <a href={att.content_url} target="_blank" className="mono" style={{marginLeft:'auto'}}>abrir</a> <a href={localUrl} target="_blank" className="mono">local</a></div>
                                    </div>
                                  ) : (
                                    <div style={{padding:'8px 10px', display:'flex', alignItems:'center', gap:8, fontSize:12}}><Icon name="fileText" size={14}/> <b>{att.file_name}</b> <span className="mono" style={{color:'var(--ink-3)'}}>{att.content_type} • {(att.size/1024).toFixed(1)} KB</span> <a href={att.content_url} target="_blank" className="btn btn--sm" style={{marginLeft:'auto'}}>Ver</a> <a href={localUrl} target="_blank" className="btn btn--sm">Descargar</a></div>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )})}
                  {comments.length===0 && <div style={{fontSize:12, color:'var(--ink-3)'}}>Sin hilo aún — backup {selected.id} en progreso si no aparece (4805/4863)</div>}
                </div>

                <div style={{marginTop:16, border:'1px solid var(--line-1)', borderRadius:8, padding:10, background:'var(--bg-1)'}}>
                  <div className="mono" style={{fontSize:11, color:'var(--ink-3)', marginBottom:6, display:'flex', alignItems:'center', gap:6}}><Icon name="mail" size={12}/> Responder — correos separados por coma</div>
                  <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:8}}>
                    <input value={toEmails} onChange={e=>setToEmails(e.target.value)} className="input" placeholder="Para (To) — ej. cliente@correo.com"/>
                    <input value={ccEmails} onChange={e=>setCcEmails(e.target.value)} className="input" placeholder="CC — ej. otro@correo.com"/>
                  </div>
                  <textarea value={replyBody} onChange={e=>setReplyBody(e.target.value)} placeholder="Escribe tu respuesta... aparecerá en historial como en Zendesk" style={{width:'100%', minHeight:80, padding:8, border:'1px solid var(--line-1)', borderRadius:8, resize:'vertical'}}/>
                  <div style={{display:'flex', gap:6, marginTop:8, justifyContent:'flex-end'}}>
                    <button className="btn" onClick={()=>sendReply(false)} disabled={sending || !replyBody.trim()} style={{opacity: sending||!replyBody.trim()?0.6:1}}>{sending?'Enviando...':'Nota interna'}</button>
                    <button className="btn btn--primary" onClick={()=>sendReply(true)} disabled={sending || !replyBody.trim()} style={{opacity: sending||!replyBody.trim()?0.6:1}}>{sending?'Enviando...':'Enviar (público)'}</button>
                  </div>
                  <div className="mono" style={{fontSize:11, color:'var(--ink-3)', marginTop:6}}>Asunto se usa como nombre del ticket (editable arriba con lápiz). Solicitante es {selected.requester_email} — al enviar con <b>Enviar</b> se registra como correo de respuesta a {toEmails||selected.requester_email}.</div>
                </div>

                <h4 style={{margin:'16px 0 8px'}}>Auditoría — {audits.length} iteraciones</h4>
                <div style={{display:'flex', flexDirection:'column', gap:6}}>
                  {audits.slice(0,20).map((au,i)=>(
                    <div key={au.id||i} className="mono" style={{fontSize:11, padding:'6px 8px', background:'var(--bg-2)', borderRadius:6, border:'1px solid var(--line-1)'}}>
                      <div>{new Date(au.created_at).toLocaleString('es-CO')} • {au.author_name ? `${au.author_name} ${au.author_email? `<${au.author_email}>`:''}` : `#${au.author_id}`}</div>
                      {au.events?.slice(0,3).map((ev,idx)=>{
                        const prev = ev.previous_value_name || ev.previous_value
                        const curr = ev.value_name || ev.value
                        return <div key={idx} style={{color:'var(--ink-3)'}}>{ev.field_name}: {String(prev||'∅').substring(0,50)} → {String(curr||'∅').substring(0,50)}</div>
                      })}
                    </div>
                  ))}
                </div>
              </div>

              <div style={{width:280, background:'var(--bg-2)', padding:12, overflow:'auto'}}>
                <b>IA Contextual</b>
                <div style={{display:'grid', gap:6, marginTop:8}}>
                  {['Sugerir respuesta','Resumir hilo','Clasificar','Detectar urgencia','Recomendar prioridad','Traducir'].map(label=>(
                    <button key={label} className="btn" style={{justifyContent:'flex-start', gap:6}}><Icon name="sparkle" size={12}/>{label}</button>
                  ))}
                </div>
                <div style={{marginTop:16, padding:10, background:'var(--surface)', borderRadius:8, border:'1px solid var(--line-1)'}}>
                  <b>Unificación</b><div className="mono" style={{fontSize:11, color:'var(--ink-3)', marginTop:4}}>TK-XXXX</div><input placeholder="TK-..." className="input" style={{width:'100%', marginTop:6}}/><button className="btn btn--primary" style={{width:'100%', marginTop:6}}>Unificar</button>
                </div>
                <div style={{marginTop:12, fontSize:11, color:'var(--ink-3)'}}>Tags: {selected.tags?.slice(0,5).join(', ')}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
