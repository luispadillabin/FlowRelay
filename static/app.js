'use strict';
const $ = id => document.getElementById(id);
let snapshot = {events: [], counts: {}, total: 0};
function notice(text, error = false) { $('notice').textContent = text; $('notice').className = error ? 'error' : ''; }
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(`${response.status}: ${result.error}`);
  return result;
}
function sample(failures) {
  $('payload').value = JSON.stringify({event_id:`demo-${Date.now()}-${Math.random().toString(16).slice(2,6)}`, event_type:'ticket.created', payload:{ticket_id:'DEMO-1042',priority:'high',summary:'Fictional account access request',fail_until:failures}}, null, 2);
}
function cell(row, text) { const td = document.createElement('td'); td.textContent = text; row.append(td); return td; }
function render() {
  $('metrics').replaceChildren();
  for (const [label,count] of [['Received',snapshot.total],['Pending',snapshot.counts.pending||0],['Waiting retry',snapshot.counts.retry_wait||0],['Succeeded',snapshot.counts.succeeded||0],['Dead letter',snapshot.counts.dead_letter||0]]) {
    const box=document.createElement('div');box.className='metric';const title=document.createElement('span');title.textContent=label;const value=document.createElement('strong');value.textContent=count;box.append(title,value);$('metrics').append(box);
  }
  $('events').replaceChildren();
  const visible=snapshot.events.filter(e=>!$('filter').value || e.status===$('filter').value);
  for (const event of visible) {
    const row=document.createElement('tr');const td=cell(row,'');const button=document.createElement('button');button.textContent=event.event_id;button.onclick=()=>inspect(event.event_id);const type=document.createElement('small');type.textContent=event.event_type;td.append(button,type);
    const badge=document.createElement('span');badge.className=`badge ${event.status}`;badge.textContent=event.status;cell(row,'').append(badge);cell(row,`${event.attempts} / 3`);cell(row,event.next_attempt ? new Date(event.next_attempt*1000).toLocaleTimeString() : '—');$('events').append(row);
  }
  if (!visible.length) {const row=document.createElement('tr');const td=cell(row,'No events here yet. Send a scenario to begin.');td.colSpan=4;$('events').append(row);}
}
async function inspect(id) {try {$('detail').textContent=JSON.stringify(await api('/api/events/'+encodeURIComponent(id)),null,2);}catch(e){notice(e.message,true);}}
async function refresh() { snapshot=await api('/api/events');render(); }
async function action(button, task) {button.disabled=true;try {await task();}catch(e){notice(e.message,true);}finally{button.disabled=false;}}
document.querySelectorAll('[data-scenario]').forEach(b=>b.onclick=()=>sample(Number(b.dataset.scenario)));
$('send').onclick=()=>action($('send'),async()=>{const result=await api('/api/events',JSON.parse($('payload').value));await refresh();notice(result.created?'201 · Event received and queued.':'200 · Duplicate acknowledged. No extra event created.');await inspect(result.event.event_id);});
$('process').onclick=()=>action($('process'),async()=>{const result=await api('/api/process',{});await refresh();notice(result.processed?`${result.processed.event_id} → ${result.processed.status}`:'Nothing due. Wait until the retry time, then process again.');if(result.processed)await inspect(result.processed.event_id);});
$('refresh').onclick=()=>action($('refresh'),async()=>{await refresh();notice('Queue refreshed.');});
$('filter').onchange=render;
sample(0);refresh().then(()=>notice('Ready. Send a fictional event to begin.')).catch(e=>notice('Local API unavailable: '+e.message,true));
