let allJobs=[]; const saved=new Set(JSON.parse(localStorage.getItem("savedJobs")||"[]"));
const $=s=>document.querySelector(s);
function money(n){return n?new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(n):""}
function ageLabel(date){if(!date)return "";const d=Math.floor((Date.now()-new Date(date))/86400000);return d<=0?"Today":d===1?"1 day old":`${d} days old`}
function render(){
 const q=$("#search").value.toLowerCase(), loc=$("#location").value, track=$("#track").value, salaryOnly=$("#salaryOnly").checked;
 let jobs=allJobs.filter(j=>(!q||`${j.company} ${j.title} ${j.reason} ${(j.tags||[]).join(" ")}`.toLowerCase().includes(q))
   &&(!loc||j.location_type===loc)&&(!track||j.track===track)&&(!salaryOnly||(j.salary_max||0)>=150000));
 const sort=$("#sort").value;
 jobs.sort((a,b)=>sort==="newest"?new Date(b.posted_at)-new Date(a.posted_at):sort==="salary"?(b.salary_max||0)-(a.salary_max||0):(b.fit_score||0)-(a.fit_score||0));
 $("#jobs").innerHTML=""; $("#empty").hidden=jobs.length>0;
 jobs.forEach(j=>{const n=$("#jobTemplate").content.cloneNode(true);n.querySelector(".score").textContent=`${j.fit_score||0}%`;n.querySelector(".company").textContent=j.company;n.querySelector(".fresh").textContent=ageLabel(j.posted_at);const titleEl=n.querySelector(".title");
      const titleLink=document.createElement("a");
      titleLink.href=j.apply_url;
      titleLink.target="_blank";
      titleLink.rel="noopener";
      titleLink.textContent=j.title;
      titleLink.className="title-link";
      titleEl.replaceChildren(titleLink);n.querySelector(".meta").textContent=`${j.location||"Location not stated"} • ${j.track||"Leadership"}`;n.querySelector(".salary").textContent=j.salary_min?`${money(j.salary_min)}–${money(j.salary_max)} ${j.salary_period||"year"}`:"Compensation not published";n.querySelector(".reason").textContent=j.reason||"";const t=n.querySelector(".tags");(j.tags||[]).forEach(x=>{const s=document.createElement("span");s.className="tag";s.textContent=x;t.appendChild(s)});const a=n.querySelector(".apply");a.href=j.apply_url;a.textContent="Open job & apply";a.onclick=()=>{j.status="applied"};const b=n.querySelector(".save");const key=j.id||j.apply_url;if(saved.has(key)){b.textContent="Saved";b.classList.add("saved")}b.onclick=()=>{saved.has(key)?saved.delete(key):saved.add(key);localStorage.setItem("savedJobs",JSON.stringify([...saved]));render()};$("#jobs").appendChild(n)});
 const eligible=allJobs.filter(j=>(j.salary_max||0)>=150000);$("#summary").innerHTML=`<div class="metric"><strong>${jobs.length}</strong><span>visible matches</span></div><div class="metric"><strong>${eligible.length}</strong><span>$150K+ roles</span></div><div class="metric"><strong>${allJobs.filter(j=>j.location_type==="remote").length}</strong><span>remote roles</span></div><div class="metric"><strong>${allJobs.filter(j=>j.fit_score>=85).length}</strong><span>priority matches</span></div>`;
}
async function load(){const r=await fetch(`data/jobs.json?v=${Date.now()}`);const d=await r.json();allJobs=d.jobs||[];$("#updated").textContent=`Last scan: ${new Date(d.updated_at).toLocaleString()}`;const tracks=[...new Set(allJobs.map(j=>j.track).filter(Boolean))].sort();$("#track").innerHTML='<option value="">All career tracks</option>'+tracks.map(x=>`<option>${x}</option>`).join("");render()}
["search","location","track","sort","salaryOnly"].forEach(id=>$("#"+id).addEventListener("input",render));$("#refreshBtn").onclick=load;
if("serviceWorker"in navigator)navigator.serviceWorker.register("sw.js");load();