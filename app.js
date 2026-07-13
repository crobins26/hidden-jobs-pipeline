let allJobs=[];
const saved=new Set(JSON.parse(localStorage.getItem("savedJobs")||"[]"));
const tracking=JSON.parse(localStorage.getItem("jobTracking")||"{}");
const interviews=JSON.parse(localStorage.getItem("interviews")||"[]");
const settings=JSON.parse(localStorage.getItem("careerSettings")||'{"weeklyGoal":25,"dailyGoal":5}');

const STATUSES=["New","Saved","Resume Tailored","Applied","Recruiter Contacted","Interview 1","Interview 2","Final Interview","Offer","Rejected","Withdrawn"];
const $=s=>document.querySelector(s);
const $$=s=>[...document.querySelectorAll(s)];

function persist(){localStorage.setItem("jobTracking",JSON.stringify(tracking));localStorage.setItem("interviews",JSON.stringify(interviews));localStorage.setItem("careerSettings",JSON.stringify(settings))}
function money(n){return n?new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(n):""}
function ageLabel(date){if(!date)return "";const d=Math.floor((Date.now()-new Date(date))/86400000);return d<=0?"Today":d===1?"1 day old":`${d} days old`}
function startOfWeek(date=new Date()){const d=new Date(date);const day=(d.getDay()+6)%7;d.setHours(0,0,0,0);d.setDate(d.getDate()-day);return d}
function todayStart(){const d=new Date();d.setHours(0,0,0,0);return d}
function isAppliedStatus(s){return ["Applied","Recruiter Contacted","Interview 1","Interview 2","Final Interview","Offer","Rejected","Withdrawn"].includes(s)}
function appliedRecords(){return Object.values(tracking).filter(r=>isAppliedStatus(r.status)&&r.appliedDate)}
function appliedThisWeek(){const start=startOfWeek();return appliedRecords().filter(r=>new Date(r.appliedDate+"T12:00:00")>=start).length}
function appliedToday(){const start=todayStart();return appliedRecords().filter(r=>new Date(r.appliedDate+"T12:00:00")>=start).length}
function pct(a,b){return b?Math.round(a/b*100):0}
function keyFor(j){return j.id||j.apply_url}
function currentRecord(j){return tracking[keyFor(j)]||{}}

function showTab(name){
  $$(".tab").forEach(b=>b.classList.toggle("active",b.dataset.tab===name));
  $$(".view").forEach(v=>v.classList.remove("active"));
  $("#"+name+"View").classList.add("active");
  if(name==="dashboard")renderDashboard();
  if(name==="pipeline")renderPipeline();
  if(name==="interviews")renderInterviews();
}
$$(".tab").forEach(b=>b.onclick=()=>showTab(b.dataset.tab));

function renderDashboard(){
  const applied=appliedRecords();
  const interviewsCount=Object.values(tracking).filter(r=>["Interview 1","Interview 2","Final Interview"].includes(r.status)).length;
  const offers=Object.values(tracking).filter(r=>r.status==="Offer").length;
  const rejections=Object.values(tracking).filter(r=>r.status==="Rejected").length;
  $("#summary").innerHTML=`
    <div class="metric"><strong>${allJobs.length}</strong><span>current matches</span></div>
    <div class="metric"><strong>${appliedThisWeek()}</strong><span>applied this week</span></div>
    <div class="metric"><strong>${interviewsCount}</strong><span>active interviews</span></div>
    <div class="metric"><strong>${offers}</strong><span>offers</span></div>
    <div class="metric"><strong>${rejections}</strong><span>rejections</span></div>`;
  $("#weeklyApplied").textContent=appliedThisWeek();$("#weeklyGoal").textContent=settings.weeklyGoal;
  $("#weeklyProgress").style.width=Math.min(100,pct(appliedThisWeek(),settings.weeklyGoal))+"%";
  $("#goalMessage").textContent=appliedThisWeek()>=settings.weeklyGoal?"Goal complete. Keep the quality bar high.":`${Math.max(0,settings.weeklyGoal-appliedThisWeek())} more applications to reach this week's goal.`;
  $("#todayApplied").textContent=appliedToday();$("#dailyGoal").textContent=settings.dailyGoal;
  $("#dailyProgress").style.width=Math.min(100,pct(appliedToday(),settings.dailyGoal))+"%";

  const counts={};STATUSES.forEach(s=>counts[s]=0);Object.values(tracking).forEach(r=>counts[r.status||"New"]=(counts[r.status||"New"]||0)+1);
  $("#funnel").innerHTML=["Applied","Recruiter Contacted","Interview 1","Interview 2","Final Interview","Offer","Rejected"].map(s=>`<div class="funnel-row"><span>${s}</span><strong>${counts[s]||0}</strong></div>`).join("");

  const resumes={};
  applied.forEach(r=>{const k=r.resumeUsed||"Not recorded";resumes[k]??={apps:0,interviews:0};resumes[k].apps++;if(["Interview 1","Interview 2","Final Interview","Offer"].includes(r.status))resumes[k].interviews++});
  $("#resumePerformance").innerHTML=Object.keys(resumes).length?Object.entries(resumes).map(([k,v])=>`<div class="resume-row"><span>${k}</span><strong>${v.apps} apps · ${pct(v.interviews,v.apps)}% interview</strong></div>`).join(""):'<p class="muted">Resume performance appears after applications are tracked.</p>';

  const today=new Date();today.setHours(0,0,0,0);
  const due=Object.entries(tracking).filter(([k,r])=>r.followUpDate&&new Date(r.followUpDate+"T12:00:00")<=today&&!["Offer","Rejected","Withdrawn"].includes(r.status)).sort((a,b)=>a[1].followUpDate.localeCompare(b[1].followUpDate));
  $("#followupsDue").innerHTML=due.length?due.slice(0,8).map(([k,r])=>`<div class="follow-row"><span>${r.company}<br><small>${r.title}</small></span><strong>${r.followUpDate}</strong></div>`).join(""):'<p class="muted">No follow-ups are due.</p>';
}

function renderJobs(){
 const q=$("#search").value.toLowerCase(),loc=$("#location").value,track=$("#track").value,salaryOnly=$("#salaryOnly").checked;
 let jobs=allJobs.filter(j=>(!q||`${j.company} ${j.title} ${j.reason} ${(j.tags||[]).join(" ")}`.toLowerCase().includes(q))&&(!loc||j.location_type===loc)&&(!track||j.track===track)&&(!salaryOnly||(j.salary_max||0)>=150000));
 const sort=$("#sort").value;
 jobs.sort((a,b)=>sort==="newest"?new Date(b.posted_at)-new Date(a.posted_at):sort==="salary"?(b.salary_max||0)-(a.salary_max||0):(b.fit_score||0)-(a.fit_score||0));
 $("#jobs").innerHTML="";$("#empty").hidden=jobs.length>0;
 jobs.forEach(j=>{
   const n=$("#jobTemplate").content.cloneNode(true),key=keyFor(j),rec=currentRecord(j);
   n.querySelector(".score").textContent=`${j.fit_score||0}%`;
   n.querySelector(".company").textContent=j.company;n.querySelector(".fresh").textContent=ageLabel(j.posted_at);
   const link=document.createElement("a");link.href=j.apply_url;link.target="_blank";link.rel="noopener";link.textContent=j.title;link.className="title-link";n.querySelector(".title").replaceChildren(link);
   n.querySelector(".meta").textContent=`${j.location||"Location not stated"} • ${j.track||"Leadership"}`;
   n.querySelector(".salary").textContent=j.salary_min?`${money(j.salary_min)}–${money(j.salary_max)} ${j.salary_period||"year"}`:"Compensation not published";
   n.querySelector(".reason").textContent=j.reason||"";
   const tags=n.querySelector(".tags");(j.tags||[]).forEach(x=>{const s=document.createElement("span");s.className="tag";s.textContent=x;tags.appendChild(s)});
   if(rec.status)n.querySelector(".status-line").innerHTML=`<span class="status-badge">${rec.status}</span>${rec.appliedDate?` · Applied ${rec.appliedDate}`:""}`;
   const a=n.querySelector(".apply");a.href=j.apply_url;
   n.querySelector(".track-btn").textContent=rec.status?"Update":"Track";
   n.querySelector(".track-btn").onclick=()=>openJobDialog(j);
   const b=n.querySelector(".save");if(saved.has(key)){b.textContent="Saved";b.classList.add("saved")}
   b.onclick=()=>{saved.has(key)?saved.delete(key):saved.add(key);localStorage.setItem("savedJobs",JSON.stringify([...saved]));renderJobs()};
   $("#jobs").appendChild(n);
 });
}

function openJobDialog(j){
 const key=keyFor(j),r=tracking[key]||{};
 $("#jobKey").value=key;$("#dialogTitle").textContent=`Track: ${j.company}`;
 $("#jobStatus").innerHTML=STATUSES.map(s=>`<option ${s===(r.status||"New")?"selected":""}>${s}</option>`).join("");
 $("#appliedDate").value=r.appliedDate||"";$("#followUpDate").value=r.followUpDate||"";$("#resumeUsed").value=r.resumeUsed||"";$("#coverLetterUsed").value=r.coverLetterUsed||"";$("#recruiterName").value=r.recruiterName||"";$("#jobNotes").value=r.notes||"";
 $("#jobDialog").showModal();
 $("#saveJobBtn").onclick=e=>{e.preventDefault();const status=$("#jobStatus").value;let appliedDate=$("#appliedDate").value;if(isAppliedStatus(status)&&!appliedDate)appliedDate=new Date().toISOString().slice(0,10);tracking[key]={...r,jobKey:key,company:j.company,title:j.title,applyUrl:j.apply_url,salaryMin:j.salary_min||null,salaryMax:j.salary_max||null,status,appliedDate,followUpDate:$("#followUpDate").value,resumeUsed:$("#resumeUsed").value,coverLetterUsed:$("#coverLetterUsed").value,recruiterName:$("#recruiterName").value,notes:$("#jobNotes").value,updatedAt:new Date().toISOString()};persist();$("#jobDialog").close();renderJobs();renderDashboard()};
}

function renderPipeline(){
 const status=$("#pipelineStatusFilter").value,q=$("#pipelineSearch").value.toLowerCase();
 const rows=Object.values(tracking).filter(r=>(!status||r.status===status)&&(!q||`${r.company} ${r.title} ${r.status} ${r.notes||""}`.toLowerCase().includes(q))).sort((a,b)=>(b.appliedDate||b.updatedAt||"").localeCompare(a.appliedDate||a.updatedAt||""));
 $("#pipelineTableWrap").innerHTML=rows.length?`<table class="pipeline-table"><thead><tr><th>Company / Role</th><th>Status</th><th>Applied</th><th>Follow-up</th><th>Resume</th><th>Action</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${r.company}</strong><br>${r.title}</td><td>${r.status||""}</td><td>${r.appliedDate||""}</td><td>${r.followUpDate||""}</td><td>${r.resumeUsed||""}</td><td><button class="small-btn edit-track" data-key="${r.jobKey}">Edit</button></td></tr>`).join("")}</tbody></table>`:'<p class="muted">No tracked applications yet.</p>';
 $$(".edit-track").forEach(b=>b.onclick=()=>{const r=tracking[b.dataset.key];const j=allJobs.find(x=>keyFor(x)===b.dataset.key)||{id:r.jobKey,company:r.company,title:r.title,apply_url:r.applyUrl,salary_min:r.salaryMin,salary_max:r.salaryMax};openJobDialog(j)});
}

function renderInterviews(){
 $("#interviewList").innerHTML=interviews.length?interviews.sort((a,b)=>a.date.localeCompare(b.date)).map((x,i)=>`<article class="interview-card"><h3>${x.company} — ${x.role}</h3><p><strong>${new Date(x.date).toLocaleString()}</strong> · ${x.round||"Interview"}</p><p>${x.interviewer?`Interviewer: ${x.interviewer}`:""}</p><p>${x.notes||""}</p><p>Research ${x.research?"✓":"—"} · STAR stories ${x.stories?"✓":"—"} · Thank-you ${x.thankYou?"✓":"—"}</p><button class="small-btn delete-interview" data-i="${i}">Delete</button></article>`).join(""):'<p class="muted">No interviews scheduled yet.</p>';
 $$(".delete-interview").forEach(b=>b.onclick=()=>{interviews.splice(Number(b.dataset.i),1);persist();renderInterviews()});
}

function exportCSV(){
 const rows=Object.values(tracking),heads=["Company","Role","Status","Applied Date","Follow-up Date","Resume Used","Cover Letter","Recruiter","Notes","Apply URL"];
 const esc=v=>`"${String(v||"").replaceAll('"','""')}"`;
 const csv=[heads.map(esc).join(","),...rows.map(r=>[r.company,r.title,r.status,r.appliedDate,r.followUpDate,r.resumeUsed,r.coverLetterUsed,r.recruiterName,r.notes,r.applyUrl].map(esc).join(","))].join("\n");
 const blob=new Blob([csv],{type:"text/csv"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=`career-pipeline-${new Date().toISOString().slice(0,10)}.csv`;a.click();URL.revokeObjectURL(url);
}

async function load(){
 const r=await fetch(`data/jobs.json?v=${Date.now()}`),d=await r.json();allJobs=d.jobs||[];$("#updated").textContent=`Last scan: ${new Date(d.updated_at).toLocaleString()}`;
 const tracks=[...new Set(allJobs.map(j=>j.track).filter(Boolean))].sort();$("#track").innerHTML='<option value="">All career tracks</option>'+tracks.map(x=>`<option>${x}</option>`).join("");
 renderJobs();renderDashboard();
}
["search","location","track","sort","salaryOnly"].forEach(id=>$("#"+id).addEventListener("input",renderJobs));
$("#pipelineStatusFilter").innerHTML='<option value="">All statuses</option>'+STATUSES.map(s=>`<option>${s}</option>`).join("");
$("#pipelineStatusFilter").oninput=renderPipeline;$("#pipelineSearch").oninput=renderPipeline;
$("#refreshBtn").onclick=load;$("#exportBtn").onclick=exportCSV;
$("#editGoalBtn").onclick=()=>{const v=Number(prompt("Weekly application goal:",settings.weeklyGoal));if(v>0){settings.weeklyGoal=v;persist();renderDashboard()}};
$("#editDailyGoalBtn").onclick=()=>{const v=Number(prompt("Daily application goal:",settings.dailyGoal));if(v>0){settings.dailyGoal=v;persist();renderDashboard()}};
$("#addInterviewBtn").onclick=()=>$("#interviewDialog").showModal();
$("#saveInterviewBtn").onclick=e=>{e.preventDefault();interviews.push({company:$("#intCompany").value,role:$("#intRole").value,date:$("#intDate").value,round:$("#intRound").value,interviewer:$("#intInterviewer").value,notes:$("#intNotes").value,research:$("#intResearch").checked,stories:$("#intStories").checked,thankYou:$("#intThankYou").checked});persist();$("#interviewForm").reset();$("#interviewDialog").close();renderInterviews()};
if("serviceWorker"in navigator)navigator.serviceWorker.register("sw.js");
load();