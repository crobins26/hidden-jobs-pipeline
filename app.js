let allJobs=[];
const saved=new Set(JSON.parse(localStorage.getItem("savedJobs")||"[]"));
const savedArchive=JSON.parse(localStorage.getItem("savedJobArchive")||"{}");
const tracking=JSON.parse(localStorage.getItem("jobTracking")||"{}");
const interviews=JSON.parse(localStorage.getItem("interviews")||"[]");
const settings=JSON.parse(localStorage.getItem("careerSettings")||'{"weeklyGoal":25,"dailyGoal":5}');

const STATUSES=["New","Saved","Resume Tailored","Applied","Recruiter Contacted","Interview 1","Interview 2","Final Interview","Offer","Rejected","Withdrawn"];
const $=s=>document.querySelector(s);
const $$=s=>[...document.querySelectorAll(s)];

function persist(){
  localStorage.setItem("jobTracking",JSON.stringify(tracking));
  localStorage.setItem("interviews",JSON.stringify(interviews));
  localStorage.setItem("careerSettings",JSON.stringify(settings));
  localStorage.setItem("savedJobs",JSON.stringify([...saved]));
  localStorage.setItem("savedJobArchive",JSON.stringify(savedArchive));
  scheduleCloudPush();
}
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
  if(name==="dashboard"){renderDashboard();renderSourceCoverage();}
  if(name==="pipeline")renderPipeline();
  if(name==="saved")renderSavedJobs();
  if(name==="interviews")renderInterviews();
  if(name==="resume")renderResumeStudio();
}
$$(".tab").forEach(b=>b.onclick=()=>showTab(b.dataset.tab));

function renderDashboard(){
  const applied=appliedRecords();
  const interviewsCount=Object.values(tracking).filter(r=>["Interview 1","Interview 2","Final Interview"].includes(r.status)).length;
  const offers=Object.values(tracking).filter(r=>r.status==="Offer").length;
  const rejections=Object.values(tracking).filter(r=>r.status==="Rejected").length;
  $("#summary").innerHTML=`
    <div class="metric"><strong>${allJobs.length}</strong><span>current matches</span></div><div class="metric"><strong>${saved.size}</strong><span>permanent saved jobs</span></div>
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
 let jobs=allJobs.filter(j=>(!q||`${j.company} ${j.title} ${j.reason} ${(j.tags||[]).join(" ")}`.toLowerCase().includes(q))&&(!loc||j.location_type===loc)&&(!track||j.track===track)&&(!salaryOnly||(j.salary_max||0)>=130000));
 const sort=$("#sort").value;
 jobs.sort((a,b)=>sort==="newest"?new Date(b.posted_at)-new Date(a.posted_at):sort==="salary"?(b.salary_max||0)-(a.salary_max||0):(b.fit_score||0)-(a.fit_score||0));
 $("#jobs").innerHTML="";$("#empty").hidden=jobs.length>0;
 jobs.forEach(j=>{
   const n=$("#jobTemplate").content.cloneNode(true),key=keyFor(j),rec=currentRecord(j);
   n.querySelector(".score").textContent=`${j.fit_score||0}%`;
   n.querySelector(".company").textContent=j.company;
   n.querySelector(".fresh").textContent=j.freshness||ageLabel(j.posted_at);
   const discoveryBadge=n.querySelector(".discovery-badge");
   if(discoveryBadge){
     discoveryBadge.hidden=!j.discovery_status;
     discoveryBadge.textContent=j.discovery_status||"";
     discoveryBadge.dataset.status=(j.discovery_status||"").toLowerCase().replaceAll(" ","-");
   }
   const topTen=n.querySelector(".top-ten-badge");
   if(topTen){topTen.hidden=!j.top_10_today;}
   const link=document.createElement("a");link.href=j.apply_url;link.target="_blank";link.rel="noopener";link.textContent=j.title;link.className="title-link";n.querySelector(".title").replaceChildren(link);
   n.querySelector(".meta").textContent=`${j.location||"Location not stated"} • ${j.track||"Leadership"}`;
   n.querySelector(".salary").textContent=j.salary_min?`${money(j.salary_min)}–${money(j.salary_max)} ${j.salary_period||"year"}`:"Compensation not published";
   n.querySelector(".reason").textContent=j.reason||"";
   const probability=j.interview_probability||(
      (j.fit_score||0)>=86?"High":(j.fit_score||0)>=72?"Medium":"Low"
   );
   n.querySelector(".probability").textContent=probability;
   n.querySelector(".probability").dataset.level=probability.toLowerCase();
   n.querySelector(".apply-time").textContent=`${j.application_time_minutes||((j.fit_score||0)>=86?15:(j.fit_score||0)>=72?25:40)} min`;
   n.querySelector(".resume-use").textContent=j.recommended_resume||(
      ["Customer Success","Customer Experience","Strategic Accounts","Enablement"].includes(j.track)
      ?"Customer Success Leadership":
      ["Commercial Operations","Sales Operations"].includes(j.track)
      ?"Commercial Operations":
      "Business Transformation"
   );
   n.querySelector(".cover-use").textContent=j.cover_letter||((j.priority_bucket==="Stretch"||(j.fit_score||0)<82)?"Recommended":"Optional");
   n.querySelector(".risk").textContent=`Main risk: ${j.main_risk||"No major gap detected"}`;
   const sourceLine=n.querySelector(".source-line");
   if(sourceLine){
     const sources=j.sources?.filter(Boolean)||[j.source].filter(Boolean);
     sourceLine.textContent=`Source: ${sources.join(" + ")||"Direct employer"}${j.source_quality>=3?" · official/direct link preferred":""}`;
   }
   const tags=n.querySelector(".tags");(j.tags||[]).forEach(x=>{const s=document.createElement("span");s.className="tag";s.textContent=x;tags.appendChild(s)});
   const bucket=j.priority_bucket?`<span class="status-badge priority-${j.priority_bucket.toLowerCase().replaceAll(" ","-")}">${j.priority_bucket}</span>`:"";
   const trackedStatus=rec.status?`<span class="status-badge">${rec.status}</span>${rec.appliedDate?` · Applied ${rec.appliedDate}`:""}`:"";
   n.querySelector(".status-line").innerHTML=[bucket,trackedStatus].filter(Boolean).join(" ");
   const a=n.querySelector(".apply");a.href=j.apply_url;
   n.querySelector(".track-btn").textContent=rec.status?"Update":"Track";
   n.querySelector(".pack-btn").onclick=()=>openApplicationPack(j);
   n.querySelector(".track-btn").onclick=()=>openJobDialog(j);
   const b=n.querySelector(".save");
   if(saved.has(key)){b.textContent="Saved";b.classList.add("saved")}
   b.onclick=()=>{
      if(saved.has(key)){
         const remove=confirm("Remove this job from Permanent Saved Jobs?");
         if(!remove)return;
         saved.delete(key);
         delete savedArchive[key];
      }else{
         saved.add(key);
         savedArchive[key]={
           ...j,
           jobKey:key,
           savedAt:new Date().toISOString(),
           archivedAt:new Date().toISOString()
         };
      }
      persist();
      renderJobs();
      renderDashboard();
   };
   $("#jobs").appendChild(n);
 });
}

function openJobDialog(j){
 const key=keyFor(j),r=tracking[key]||{};
 $("#jobKey").value=key;$("#dialogTitle").textContent=`Track: ${j.company}`;
 $("#jobStatus").innerHTML=STATUSES.map(s=>`<option ${s===(r.status||"New")?"selected":""}>${s}</option>`).join("");
 $("#appliedDate").value=r.appliedDate||"";$("#followUpDate").value=r.followUpDate||"";$("#resumeUsed").value=r.resumeUsed||"";$("#coverLetterUsed").value=r.coverLetterUsed||"";$("#recruiterName").value=r.recruiterName||"";$("#jobNotes").value=r.notes||"";
 $("#jobDialog").showModal();
 $("#saveJobBtn").onclick=e=>{e.preventDefault();const status=$("#jobStatus").value;let appliedDate=$("#appliedDate").value;if(isAppliedStatus(status)&&!appliedDate)appliedDate=new Date().toISOString().slice(0,10);tracking[key]={...r,jobKey:key,company:j.company,title:j.title,applyUrl:j.apply_url,salaryMin:j.salary_min||null,salaryMax:j.salary_max||null,status,appliedDate,followUpDate:$("#followUpDate").value,resumeUsed:$("#resumeUsed").value,coverLetterUsed:$("#coverLetterUsed").value,recruiterName:$("#recruiterName").value,notes:$("#jobNotes").value,updatedAt:new Date().toISOString()};
saved.add(key);
savedArchive[key]={
  ...(savedArchive[key]||{}),
  ...j,
  jobKey:key,
  savedAt:(savedArchive[key]||{}).savedAt||new Date().toISOString(),
  archivedAt:new Date().toISOString()
};
persist();$("#jobDialog").close();renderJobs();renderDashboard()};
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
 const r=await fetch(`data/jobs.json?v=${Date.now()}`,{cache:"no-store"}),d=await r.json();
 allJobs=d.jobs||[];
 $("#updated").textContent=`Last scan: ${new Date(d.updated_at).toLocaleString()}`;
 const engine=$("#engineStatus");
 if(engine){
   const providers=d.provider_status||{};
   const activeProviders=Object.entries(providers)
     .filter(([,value])=>value?.active)
     .map(([name])=>name==="direct_ats"?"Direct ATS":name.charAt(0).toUpperCase()+name.slice(1));
   engine.textContent=`Engine v14.0 · ${activeProviders.join(" + ")||"Fallback only"} · ${d.match_count??allJobs.length} matches`;
   engine.classList.toggle("engine-active",Boolean(d.broad_search_enabled));
 }
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

/* ---------------- Resume Studio ---------------- */
let masterResumeText=localStorage.getItem("masterResumeText")||"";
let masterResumeFileName=localStorage.getItem("masterResumeFileName")||"";
let lastResumeAnalysis=null;

const STOP_WORDS=new Set([
 "the","and","or","to","of","in","for","with","a","an","on","is","are","as","at","by","from","this","that",
 "will","be","we","you","your","our","their","they","it","have","has","had","who","what","when","where","why",
 "job","role","team","work","working","company","position","required","preferred","including","across","within"
]);

const ROLE_TRACKS={
 "Customer Success":["customer success","client success","retention","renewal","adoption","churn","customer health","nps","qbr","onboarding"],
 "Revenue Operations":["revenue operations","revops","forecasting","pipeline","salesforce","go-to-market","gtm","sales operations"],
 "Commercial Operations":["commercial operations","pricing","promotion","retail","distribution","commercial strategy","revenue growth"],
 "Business Transformation":["business transformation","change management","operational excellence","automation","process redesign","continuous improvement"],
 "Business Operations":["business operations","strategy and operations","kpi","dashboard","business intelligence","cross-functional","executive reporting"],
 "Strategic Accounts":["strategic accounts","enterprise accounts","account management","expansion","executive relationships","commercial negotiations"],
 "Implementation":["implementation","professional services","deployment","onboarding","project management","customer delivery"]
};

function renderResumeStudio(){
  const status=$("#resumeFileStatus");
  if(status&&masterResumeText){
    status.textContent=`Master résumé ready: ${masterResumeFileName||"Saved résumé"} · ${masterResumeText.length.toLocaleString()} characters`;
  }
}

function tokenize(text){
  return (text.toLowerCase().match(/[a-z][a-z0-9+#.&-]{2,}/g)||[])
    .map(x=>x.replace(/[.,]/g,""))
    .filter(x=>!STOP_WORDS.has(x));
}

function phrases(text){
  const lower=text.toLowerCase();
  const library=[
    "customer success","client success","customer experience","revenue operations","commercial operations",
    "business operations","sales operations","operational excellence","business transformation","change management",
    "process improvement","process automation","cross-functional leadership","executive reporting","strategic planning",
    "account management","customer retention","customer adoption","renewal strategy","revenue growth","salesforce",
    "power bi","tableau","sql","advanced excel","kpi development","business intelligence","forecasting",
    "strategic accounts","professional services","implementation","enablement","program management"
  ];
  return library.filter(p=>lower.includes(p));
}

function topKeywords(text,limit=30){
  const counts={};
  tokenize(text).forEach(w=>counts[w]=(counts[w]||0)+1);
  phrases(text).forEach(p=>counts[p]=(counts[p]||0)+4);
  return Object.entries(counts)
    .sort((a,b)=>b[1]-a[1])
    .slice(0,limit)
    .map(([word,count])=>({word,count}));
}

function detectTrack(jd){
  const t=jd.toLowerCase();
  let best={track:"Business Operations",score:0};
  Object.entries(ROLE_TRACKS).forEach(([track,terms])=>{
    const score=terms.reduce((n,x)=>n+(t.includes(x)?1:0),0);
    if(score>best.score)best={track,score};
  });
  return best.track;
}

function splitResumeSections(text){
  const lines=text.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  const bullets=lines.filter(x=>/^[-•●▪]/.test(x)||x.length>70);
  return {lines,bullets};
}

function analyzeResume(){
  const jd=$("#jobDescription").value.trim();
  if(!masterResumeText){alert("Upload your master résumé first.");return null}
  if(!jd){alert("Paste the job description first.");return null}

  const jdKeys=topKeywords(jd,35);
  const resumeLower=masterResumeText.toLowerCase();
  const hits=jdKeys.filter(k=>resumeLower.includes(k.word));
  const misses=jdKeys.filter(k=>!resumeLower.includes(k.word));
  const score=Math.min(98,Math.round((hits.reduce((n,k)=>n+k.count,0)/Math.max(1,jdKeys.reduce((n,k)=>n+k.count,0)))*100)+18);
  const track=detectTrack(jd);

  lastResumeAnalysis={jd,jdKeys,hits,misses,score,track};
  $("#resumeMatchScore").textContent=score+"%";
  $("#resumeTrack").textContent=`Recommended résumé lane: ${track}`;
  $("#resumeKeywords").innerHTML=`<div class="keyword-cloud">${
    hits.slice(0,15).map(k=>`<span class="keyword-hit">✓ ${k.word}</span>`).join("")
  }${
    misses.slice(0,12).map(k=>`<span class="keyword-miss">+ ${k.word}</span>`).join("")
  }</div>`;

  const cover=score<82 || /cover letter|required cover/i.test(jd);
  $("#resumeStrategy").innerHTML=`
    <p><strong>Resume:</strong> Use the ${track} version.</p>
    <p><strong>Cover letter:</strong> ${cover?"Recommended":"Optional unless requested"}.</p>
    <p><strong>Tailoring priority:</strong> Add evidence for ${misses.slice(0,6).map(k=>k.word).join(", ")||"the strongest repeated requirements"}.</p>
    <p><strong>Application effort:</strong> ${score>=88?"15–20 minutes":score>=78?"25–35 minutes":"45+ minutes; review whether the gap is worth it"}.</p>`;
  return lastResumeAnalysis;
}

function sentenceCase(s){return s.charAt(0).toUpperCase()+s.slice(1)}

function chooseBullets(jd,bullets,limit=16){
  const keys=topKeywords(jd,40).map(x=>x.word);
  return bullets.map(b=>{
    const lower=b.toLowerCase();
    const score=keys.reduce((n,k)=>n+(lower.includes(k)?(k.includes(" ")?4:1):0),0)
      +(lower.match(/\d+%|\$[\d,.]+|[\d,]+\+?/g)||[]).length*2;
    return {bullet:b.replace(/^[-•●▪]\s*/,""),score};
  }).sort((a,b)=>b.score-a.score).slice(0,limit);
}

function extractContactAndEducation(lines){
  const contact=lines.slice(0,8);
  const educationStart=lines.findIndex(x=>/^education$/i.test(x));
  const certStart=lines.findIndex(x=>/^certifications/i.test(x));
  return {
    contact,
    education:educationStart>=0?lines.slice(educationStart,certStart>educationStart?certStart:educationStart+10):[],
    certifications:certStart>=0?lines.slice(certStart,certStart+18):[]
  };
}

function generateTailoredResume(){
  const analysis=lastResumeAnalysis||analyzeResume();
  if(!analysis)return;

  const {lines,bullets}=splitResumeSections(masterResumeText);
  const selected=chooseBullets(analysis.jd,bullets,18);
  const extra=extractContactAndEducation(lines);
  const topSkills=[...analysis.hits.map(x=>x.word),...analysis.misses.slice(0,5).map(x=>x.word)]
    .filter((x,i,a)=>a.indexOf(x)===i).slice(0,18);

  const titleMatch=analysis.jd.match(/(?:director|senior manager|sr\.? manager|head|vice president|vp)[^\n]{0,80}/i);
  const targetTitle=titleMatch?sentenceCase(titleMatch[0].trim()):analysis.track+" Leader";

  const summary=`Strategic ${analysis.track} leader with 15+ years of experience improving customer outcomes, commercial execution, operational visibility, and business performance. Leads cross-functional initiatives supporting approximately $100M in annual business, builds executive KPI reporting, and redesigns workflows to improve speed, accuracy, accountability, and scalability. Brings deep experience in analytics, process automation, enterprise stakeholder management, and data-driven decision-making.`;

  const output=[
    ...extra.contact.slice(0,4),
    "",
    targetTitle.toUpperCase(),
    "",
    "PROFESSIONAL SUMMARY",
    summary,
    "",
    "CORE EXPERTISE",
    topSkills.map(sentenceCase).join(" | "),
    "",
    "SELECTED CAREER ACHIEVEMENTS",
    ...selected.slice(0,8).map(x=>"• "+x.bullet),
    "",
    "PROFESSIONAL EXPERIENCE",
    ...selected.slice(8).map(x=>"• "+x.bullet),
    "",
    ...extra.education,
    "",
    ...extra.certifications
  ].join("\n");

  $("#generatedResume").value=output;
}

function downloadWord(){
  const text=$("#generatedResume").value.trim();
  if(!text){alert("Generate the résumé first.");return}
  const html=`<!doctype html><html><head><meta charset="utf-8"><style>
  body{font-family:Arial,sans-serif;font-size:10.5pt;line-height:1.25;margin:.65in;color:#111}
  h1{font-size:18pt}p{margin:0 0 6pt}pre{white-space:pre-wrap;font-family:Arial,sans-serif}
  </style></head><body><pre>${text.replace(/&/g,"&amp;").replace(/</g,"&lt;")}</pre></body></html>`;
  const blob=new Blob([html],{type:"application/msword"});
  const url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download="Tailored_Resume_Cernice_Robinson.doc";a.click();URL.revokeObjectURL(url);
}

function copyAIRewritePrompt(){
  const jd=$("#jobDescription").value.trim(),draft=$("#generatedResume").value.trim();
  if(!jd||!masterResumeText){alert("Upload the résumé and paste the job description first.");return}
  const prompt=`Act as an expert executive resume writer. Tailor my master resume to the job description below. Preserve factual accuracy. Do not invent experience, employers, tools, degrees, or metrics. Use ATS-friendly language, achievement-focused bullets, and a concise executive summary. Prioritize the most relevant experience and keywords naturally. Return a complete two-to-three-page resume.

JOB DESCRIPTION:
${jd}

MASTER RESUME:
${masterResumeText}

CURRENT RULES-BASED DRAFT:
${draft}`;
  navigator.clipboard.writeText(prompt);
  alert("AI rewrite prompt copied. Paste it into ChatGPT.");
}

$("#resumeFile").addEventListener("change",async e=>{
  const file=e.target.files[0];
  if(!file)return;
  try{
    if(typeof mammoth==="undefined")throw new Error("DOCX reader did not load. Check your internet connection.");
    const buffer=await file.arrayBuffer();
    const result=await mammoth.extractRawText({arrayBuffer:buffer});
    masterResumeText=result.value.trim();
    masterResumeFileName=file.name;
    localStorage.setItem("masterResumeText",masterResumeText);
    localStorage.setItem("masterResumeFileName",masterResumeFileName);
    $("#resumeFileStatus").textContent=`Loaded and saved: ${file.name} · ${masterResumeText.length.toLocaleString()} characters`;
    scheduleCloudPush();
  }catch(err){
    $("#resumeFileStatus").textContent="Could not read the résumé: "+err.message;
  }
});
$("#analyzeResumeBtn").onclick=analyzeResume;
$("#generateResumeBtn").onclick=generateTailoredResume;
$("#copyResumeBtn").onclick=()=>{navigator.clipboard.writeText($("#generatedResume").value);alert("Resume copied.")};
$("#downloadResumeBtn").onclick=downloadWord;
$("#copyPromptBtn").onclick=copyAIRewritePrompt;


/* ---------------- Permanent Saved Jobs ---------------- */
function mergedSavedRecord(key){
  const job=savedArchive[key]||{};
  const track=tracking[key]||{};
  return {
    ...job,
    status:track.status||job.status||"Saved",
    appliedDate:track.appliedDate||"",
    followUpDate:track.followUpDate||"",
    resumeUsed:track.resumeUsed||job.recommended_resume||"",
    recruiterName:track.recruiterName||"",
    notes:track.notes||"",
    updatedAt:track.updatedAt||job.archivedAt||job.savedAt||""
  };
}

function renderSavedJobs(){
  const q=($("#savedSearch")?.value||"").toLowerCase();
  const status=$("#savedStatusFilter")?.value||"";
  const rows=[...saved].map(key=>({key,...mergedSavedRecord(key)}))
    .filter(r=>(!status||r.status===status)&&(
      !q||`${r.company||""} ${r.title||""} ${r.status||""} ${r.notes||""} ${r.track||""}`.toLowerCase().includes(q)
    ))
    .sort((a,b)=>(b.savedAt||b.updatedAt||"").localeCompare(a.savedAt||a.updatedAt||""));

  const wrap=$("#savedJobsList");
  if(!wrap)return;
  wrap.innerHTML="";

  if(!rows.length){
    wrap.innerHTML='<p class="muted">No permanent saved jobs match this filter.</p>';
    return;
  }

  rows.forEach(r=>{
    const n=$("#savedJobTemplate").content.cloneNode(true);
    n.querySelector(".saved-company").textContent=r.company||"Unknown company";
    n.querySelector(".saved-title").textContent=r.title||"Untitled role";
    n.querySelector(".saved-status").textContent=r.status||"Saved";
    n.querySelector(".saved-meta").textContent=`${r.location||"Location not stated"} · ${r.track||"Leadership"}`;
    n.querySelector(".saved-salary").textContent=r.salary_min
      ?`${money(r.salary_min)}–${money(r.salary_max)} ${r.salary_period||"year"}`
      :"Compensation not published";
    n.querySelector(".saved-dates").textContent=`Saved ${r.savedAt?new Date(r.savedAt).toLocaleDateString():""}${r.appliedDate?` · Applied ${r.appliedDate}`:""}${r.followUpDate?` · Follow up ${r.followUpDate}`:""}`;
    n.querySelector(".saved-risk").textContent=r.main_risk?`Main risk: ${r.main_risk}`:"";
    const documents=n.querySelector(".saved-documents");
    const documentList=r.documents||[];
    documents.innerHTML=documentList.length
      ?`<strong>Documents</strong><div class="document-links">${documentList.map((doc,index)=>`<button class="small-btn saved-doc-link" data-index="${index}">${doc.label||doc.type}</button>`).join("")}</div>`
      :"";
    documents.querySelectorAll(".saved-doc-link").forEach(button=>{
      button.onclick=()=>downloadStoredDocument(r.key,documentList[Number(button.dataset.index)]);
    });
    const link=n.querySelector(".saved-apply");
    link.href=r.apply_url||r.applyUrl||"#";
    n.querySelector(".saved-edit").onclick=()=>{
      const job=allJobs.find(j=>keyFor(j)===r.key)||{
        id:r.key,
        company:r.company,
        title:r.title,
        location:r.location,
        track:r.track,
        salary_min:r.salary_min||r.salaryMin,
        salary_max:r.salary_max||r.salaryMax,
        salary_period:r.salary_period||"year",
        apply_url:r.apply_url||r.applyUrl,
        fit_score:r.fit_score,
        recommended_resume:r.recommended_resume,
        main_risk:r.main_risk
      };
      openJobDialog(job);
    };
    n.querySelector(".saved-delete").onclick=()=>{
      if(!confirm(`Permanently delete ${r.company} — ${r.title} from your archive?`))return;
      saved.delete(r.key);
      delete savedArchive[r.key];
      persist();
      renderSavedJobs();
      renderDashboard();
    };
    wrap.appendChild(n);
  });
}

function exportSavedJobs(){
  const rows=[...saved].map(key=>mergedSavedRecord(key));
  const heads=["Company","Role","Status","Location","Salary Min","Salary Max","Saved Date","Applied Date","Follow-up Date","Resume Used","Recruiter","Notes","Apply URL"];
  const esc=v=>`"${String(v??"").replaceAll('"','""')}"`;
  const csv=[heads.map(esc).join(","),...rows.map(r=>[
    r.company,r.title,r.status,r.location,r.salary_min||r.salaryMin,r.salary_max||r.salaryMax,
    r.savedAt,r.appliedDate,r.followUpDate,r.resumeUsed,r.recruiterName,r.notes,r.apply_url||r.applyUrl
  ].map(esc).join(","))].join("\n");
  const blob=new Blob([csv],{type:"text/csv"});
  const url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;
  a.download=`permanent-saved-jobs-${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

if($("#savedStatusFilter")){
  $("#savedStatusFilter").innerHTML='<option value="">All statuses</option>'+STATUSES.map(s=>`<option>${s}</option>`).join("");
  $("#savedStatusFilter").oninput=renderSavedJobs;
}
if($("#savedSearch"))$("#savedSearch").oninput=renderSavedJobs;
if($("#exportSavedBtn"))$("#exportSavedBtn").onclick=exportSavedJobs;



/* ---------------- Supabase Cross-Device Sync v11 ---------------- */
let cloudClient=null;
let cloudUser=null;
let cloudSyncTimer=null;
let cloudReady=false;

function setCloudDiagnostic(message=""){
  const el=$("#cloudDiagnostic");
  if(el)el.textContent=message;
}

function cloudConfigured(){
  const url=String(window.CAREER_SUPABASE_URL||"").trim();
  const key=String(window.CAREER_SUPABASE_KEY||"").trim();

  return Boolean(
    url &&
    key &&
    /^https:\/\/[a-z0-9-]+\.supabase\.co$/i.test(url) &&
    !url.includes("/rest/v1") &&
    !url.includes("PASTE_") &&
    !key.includes("PASTE_") &&
    (key.startsWith("sb_publishable_") || key.startsWith("eyJ"))
  );
}

function setCloudStatus(message,state=""){
  const el=$("#cloudStatus");
  const bar=document.querySelector(".cloud-bar");
  if(el)el.textContent=message;
  if(bar){
    bar.classList.toggle("cloud-online",state==="online");
    bar.classList.toggle("cloud-error",state==="error");
  }
}

function cloudSnapshot(){
  return {
    saved_jobs:savedArchive,
    saved_ids:[...saved],
    tracking,
    interviews,
    settings,
    resume_profile:{masterResumeText,masterResumeFileName},
    updated_at:new Date().toISOString()
  };
}

function applyCloudSnapshot(snapshot){
  if(!snapshot)return;

  const cloudSaved=snapshot.saved_jobs||{};
  const cloudTracking=snapshot.tracking||{};

  Object.assign(savedArchive,cloudSaved);
  Object.assign(tracking,cloudTracking);
  (snapshot.saved_ids||Object.keys(cloudSaved)).forEach(id=>saved.add(id));

  if(Array.isArray(snapshot.interviews)){
    interviews.splice(0,interviews.length,...snapshot.interviews);
  }

  if(snapshot.settings){
    Object.assign(settings,snapshot.settings);
  }

  if(snapshot.resume_profile){
    masterResumeText=snapshot.resume_profile.masterResumeText||masterResumeText;
    masterResumeFileName=snapshot.resume_profile.masterResumeFileName||masterResumeFileName;
    localStorage.setItem("masterResumeText",masterResumeText);
    localStorage.setItem("masterResumeFileName",masterResumeFileName);
    const status=$("#resumeFileStatus");
    if(status&&masterResumeText){
      status.textContent=`Cloud master résumé loaded: ${masterResumeFileName||"Master résumé"}`;
    }
  }

  persistLocalOnly();
  renderJobs();
  renderDashboard();
  renderPipeline();
  renderInterviews();
  renderSavedJobs();
}

function persistLocalOnly(){
  localStorage.setItem("jobTracking",JSON.stringify(tracking));
  localStorage.setItem("interviews",JSON.stringify(interviews));
  localStorage.setItem("careerSettings",JSON.stringify(settings));
  localStorage.setItem("savedJobs",JSON.stringify([...saved]));
  localStorage.setItem("savedJobArchive",JSON.stringify(savedArchive));
}

async function pushCloudSnapshot(){
  if(!cloudReady||!cloudClient||!cloudUser)return;

  setCloudStatus("Syncing…");
  const {error}=await cloudClient
    .from("career_state")
    .upsert({
      user_id:cloudUser.id,
      state:cloudSnapshot(),
      updated_at:new Date().toISOString()
    },{onConflict:"user_id"});

  if(error){
    console.error("Supabase push error:",error);
    setCloudStatus("Sync failed","error");
    setCloudDiagnostic(error.message||"Unable to save cloud data.");
    return;
  }

  setCloudStatus(`Synced ${new Date().toLocaleTimeString()}`,"online");
  setCloudDiagnostic("Desktop and mobile share this account.");
}

async function pullCloudSnapshot(){
  if(!cloudReady||!cloudClient||!cloudUser)return;

  setCloudStatus("Loading cloud data…");
  const {data,error}=await cloudClient
    .from("career_state")
    .select("state,updated_at")
    .eq("user_id",cloudUser.id)
    .maybeSingle();

  if(error){
    console.error("Supabase read error:",error);
    setCloudStatus("Cloud read failed","error");
    setCloudDiagnostic(error.message||"Unable to read cloud data.");
    return;
  }

  if(data?.state){
    applyCloudSnapshot(data.state);
    setCloudStatus(`Synced ${new Date(data.updated_at).toLocaleString()}`,"online");
    setCloudDiagnostic("Cloud data loaded.");
  }else{
    setCloudDiagnostic("New cloud account — uploading this device.");
    await pushCloudSnapshot();
  }
}

function scheduleCloudPush(){
  if(!cloudReady||!cloudUser)return;
  clearTimeout(cloudSyncTimer);
  cloudSyncTimer=setTimeout(pushCloudSnapshot,900);
}

function updateCloudButtons(){
  const logged=Boolean(cloudUser);
  $("#cloudLoginBtn").hidden=logged;
  $("#cloudSyncBtn").hidden=!logged;
  $("#cloudLogoutBtn").hidden=!logged;

  if(logged){
    setCloudStatus(`Signed in: ${cloudUser.email}`,"online");
  }
}

async function initializeCloud(){
  setCloudStatus("Checking configuration…");
  setCloudDiagnostic("Engine v11 startup test");

  if(typeof window.supabase==="undefined"){
    cloudReady=false;
    setCloudStatus("Supabase library unavailable","error");
    setCloudDiagnostic("The Supabase browser library did not load. Refresh while online.");
    return;
  }

  if(!cloudConfigured()){
    cloudReady=false;
    setCloudStatus("Setup required","error");

    const url=String(window.CAREER_SUPABASE_URL||"");
    const key=String(window.CAREER_SUPABASE_KEY||"");

    if(url.includes("/rest/v1")){
      setCloudDiagnostic("Remove /rest/v1/ from the Supabase Project URL.");
    }else if(!url||url.includes("PASTE_")){
      setCloudDiagnostic("Project URL is missing or still contains placeholder text.");
    }else if(!key||key.includes("PASTE_")){
      setCloudDiagnostic("Publishable key is missing or still contains placeholder text.");
    }else{
      setCloudDiagnostic("Configuration format is invalid. Hard-refresh the website.");
    }
    return;
  }

  try{
    cloudClient=window.supabase.createClient(
      String(window.CAREER_SUPABASE_URL).trim(),
      String(window.CAREER_SUPABASE_KEY).trim(),
      {
        auth:{
          persistSession:true,
          autoRefreshToken:true,
          detectSessionInUrl:true
        }
      }
    );

    const {data,error}=await cloudClient.auth.getSession();
    if(error)throw error;

    cloudReady=true;
    cloudUser=data.session?.user||null;
    updateCloudButtons();

    if(cloudUser){
      await pullCloudSnapshot();
    }else{
      setCloudStatus("Ready — sign in");
      setCloudDiagnostic("Configuration confirmed.");
    }

    cloudClient.auth.onAuthStateChange(async(event,session)=>{
      cloudUser=session?.user||null;
      updateCloudButtons();

      if(cloudUser){
        await pullCloudSnapshot();
      }else{
        setCloudStatus("Ready — sign in");
        setCloudDiagnostic("Signed out.");
      }
    });
  }catch(error){
    console.error("Supabase initialization error:",error);
    cloudReady=false;
    setCloudStatus("Cloud initialization failed","error");
    setCloudDiagnostic(error.message||"Unable to initialize Supabase.");
  }
}

async function cloudSignUp(){
  if(!cloudReady)return;

  const email=$("#cloudEmail").value.trim();
  const password=$("#cloudPassword").value;

  const {data,error}=await cloudClient.auth.signUp({
    email,
    password,
    options:{
      emailRedirectTo:"https://crobins26.github.io/hidden-jobs-pipeline/"
    }
  });

  $("#cloudAuthMessage").textContent=error
    ?error.message
    :(data.session
      ?"Account created and signed in."
      :"Check your email to confirm the account, then return here.");

  if(!error&&data.session)$("#cloudAuthDialog").close();
}

async function cloudSignIn(){
  if(!cloudReady)return;

  const email=$("#cloudEmail").value.trim();
  const password=$("#cloudPassword").value;

  const {error}=await cloudClient.auth.signInWithPassword({email,password});
  $("#cloudAuthMessage").textContent=error?error.message:"Signed in.";

  if(!error)$("#cloudAuthDialog").close();
}

$("#cloudLoginBtn").onclick=()=>{
  if(!cloudReady){
    alert($("#cloudDiagnostic")?.textContent||"Cloud sync is not ready.");
    return;
  }

  $("#cloudAuthMessage").textContent="";
  $("#cloudAuthDialog").showModal();
};

$("#cloudSyncBtn").onclick=async()=>{
  await pullCloudSnapshot();
  await pushCloudSnapshot();
};

$("#cloudLogoutBtn").onclick=async()=>{
  if(cloudClient)await cloudClient.auth.signOut();
};

$("#cloudSignUpBtn").onclick=cloudSignUp;
$("#cloudSignInBtn").onclick=cloudSignIn;

window.addEventListener("load",()=>{
  setTimeout(initializeCloud,150);
});


/* ---------------- One-Click Application Pack v12 ---------------- */
let activePackJob=null;

function sanitizeFileName(value){
  return String(value||"document")
    .replace(/[^\w\s.-]/g,"")
    .replace(/\s+/g,"_")
    .slice(0,90);
}

function jobDescriptionFor(job){
  return job.job_description||
    (savedArchive[keyFor(job)]||{}).job_description||
    "";
}

function openApplicationPack(job){
  activePackJob=job;
  $("#packJobName").textContent=`${job.company} — ${job.title}`;
  $("#packJobDescription").value=jobDescriptionFor(job);
  $("#packNotes").value=(tracking[keyFor(job)]||{}).notes||"";
  $("#packMarkApplied").checked=false;
  $("#packProgress").textContent=masterResumeText
    ?"Master résumé ready."
    :"Upload your master résumé in Resume Studio before generating documents.";
  $("#applicationPackDialog").showModal();
}

function createResumeTextForJob(job,jobDescription){
  const previousDescription=$("#jobDescription").value;
  const previousOutput=$("#generatedResume").value;
  $("#jobDescription").value=jobDescription;
  lastResumeAnalysis=null;
  const analysis=analyzeResume();
  if(!analysis){
    $("#jobDescription").value=previousDescription;
    return "";
  }
  generateTailoredResume();
  const text=$("#generatedResume").value;
  $("#jobDescription").value=previousDescription;
  $("#generatedResume").value=previousOutput;
  return text;
}

function createCoverLetterText(job,jobDescription){
  const track=job.track||detectTrack(jobDescription);
  const company=job.company||"the company";
  const title=job.title||"this role";

  return `Cernice Robinson, MS
Hammond, Indiana

Dear Hiring Team,

I am applying for the ${title} position at ${company}. I bring more than 15 years of leadership experience spanning customer success, commercial operations, business transformation, analytics, and enterprise account management. My background is especially relevant to this opportunity because I have led cross-functional initiatives supporting approximately $100 million in annual commercial operations while improving customer outcomes, operational visibility, and execution discipline.

In my current leadership work, I partner across Sales, Finance, Operations, Supply Chain, Marketing, IT, and Customer Service to turn complex business requirements into practical operating systems. My results include improving promotional compliance by 36%, eliminating an estimated 780 to 1,040 labor hours annually through workflow automation, building executive dashboards and KPI frameworks, and previously generating $1.2 million in expansion revenue through consultative customer success leadership.

For a ${track} organization, I offer a combination that is difficult to find in one candidate: executive-level customer communication, hands-on process design, data-driven decision-making, change leadership, and the ability to coach teams through adoption. I am comfortable moving between strategy and execution—whether the need is improving retention, building operating cadence, strengthening customer health visibility, automating workflows, or aligning stakeholders around measurable outcomes.

I would welcome the opportunity to discuss how my experience could help ${company} strengthen customer value, scale operations, and deliver durable business results.

Sincerely,

Cernice Robinson, MS`;
}

async function createDocxBlob(title,bodyText){
  if(!window.docx)throw new Error("DOCX library is unavailable.");

  const {Document,Packer,Paragraph,TextRun,HeadingLevel}=window.docx;
  const paragraphs=bodyText.split(/\n/).map(line=>{
    const trimmed=line.trim();
    if(!trimmed)return new Paragraph({text:""});
    if(/^[A-Z][A-Z\s&/-]{4,}$/.test(trimmed)){
      return new Paragraph({
        text:trimmed,
        heading:HeadingLevel.HEADING_2,
        spacing:{before:180,after:80}
      });
    }
    if(trimmed.startsWith("•")){
      return new Paragraph({
        children:[new TextRun(trimmed.replace(/^•\s*/,""))],
        bullet:{level:0},
        spacing:{after:60}
      });
    }
    return new Paragraph({
      children:[new TextRun(trimmed)],
      spacing:{after:80}
    });
  });

  const document=new Document({
    sections:[{
      properties:{},
      children:[
        new Paragraph({
          children:[new TextRun({text:title,bold:true,size:30})],
          spacing:{after:160}
        }),
        ...paragraphs
      ]
    }]
  });

  return await Packer.toBlob(document);
}

function createPdfBlob(title,bodyText){
  if(!window.jspdf?.jsPDF)throw new Error("PDF library is unavailable.");

  const pdf=new window.jspdf.jsPDF({unit:"pt",format:"letter"});
  const margin=50;
  const width=pdf.internal.pageSize.getWidth()-margin*2;
  const height=pdf.internal.pageSize.getHeight();
  let y=55;

  pdf.setFont("helvetica","bold");
  pdf.setFontSize(16);
  pdf.text(title,margin,y);
  y+=24;

  pdf.setFont("helvetica","normal");
  pdf.setFontSize(10.5);

  const lines=pdf.splitTextToSize(bodyText,width);
  for(const line of lines){
    if(y>height-50){
      pdf.addPage();
      y=50;
    }
    pdf.text(line,margin,y);
    y+=14;
  }

  return pdf.output("blob");
}

async function uploadPrivateDocument(jobKey,fileName,blob,contentType){
  if(!cloudReady||!cloudClient||!cloudUser){
    return {stored:false,reason:"Sign in to store documents in the cloud."};
  }

  const path=`${cloudUser.id}/${sanitizeFileName(jobKey)}/${fileName}`;
  const {error}=await cloudClient.storage
    .from("career-documents")
    .upload(path,blob,{
      contentType,
      upsert:true
    });

  if(error)throw error;
  return {stored:true,path};
}

async function downloadStoredDocument(jobKey,document){
  if(!document?.path){
    alert("This document does not have a cloud-storage path.");
    return;
  }
  if(!cloudReady||!cloudClient||!cloudUser){
    alert("Sign in to download the stored document.");
    return;
  }

  const {data,error}=await cloudClient.storage
    .from("career-documents")
    .download(document.path);

  if(error){
    alert(error.message);
    return;
  }

  const url=URL.createObjectURL(data);
  const anchor=document.createElement("a");
  anchor.href=url;
  anchor.download=document.fileName||"career-document";
  anchor.click();
  URL.revokeObjectURL(url);
}

async function runApplicationPack(){
  const job=activePackJob;
  if(!job)return;

  const key=keyFor(job);
  const description=$("#packJobDescription").value.trim();
  const notes=$("#packNotes").value.trim();
  const buildResume=$("#packResume").checked;
  const buildCover=$("#packCover").checked;
  const storeFiles=$("#packStoreFiles").checked;
  const markApplied=$("#packMarkApplied").checked;

  if((buildResume||buildCover)&&!masterResumeText){
    alert("Upload your master résumé in Resume Studio first.");
    return;
  }

  if((buildResume||buildCover)&&!description){
    alert("Paste the full job description before building the application pack.");
    return;
  }

  $("#runApplicationPackBtn").disabled=true;
  $("#packProgress").textContent="Saving job…";

  try{
    saved.add(key);
    savedArchive[key]={
      ...(savedArchive[key]||{}),
      ...job,
      jobKey:key,
      job_description:description,
      savedAt:(savedArchive[key]||{}).savedAt||new Date().toISOString(),
      archivedAt:new Date().toISOString(),
      documents:[...((savedArchive[key]||{}).documents||[])]
    };

    const record=tracking[key]||{};
    tracking[key]={
      ...record,
      jobKey:key,
      company:job.company,
      title:job.title,
      applyUrl:job.apply_url,
      salaryMin:job.salary_min||null,
      salaryMax:job.salary_max||null,
      status:markApplied?"Applied":"Resume Tailored",
      appliedDate:markApplied?(record.appliedDate||new Date().toISOString().slice(0,10)):(record.appliedDate||""),
      followUpDate:record.followUpDate||"",
      resumeUsed:job.recommended_resume||record.resumeUsed||"",
      coverLetterUsed:buildCover?"Yes":record.coverLetterUsed||"",
      recruiterName:record.recruiterName||"",
      notes:notes||record.notes||"",
      interviewNotes:record.interviewNotes||{
        researchCompleted:false,
        starStoriesReady:false,
        questions:[],
        notes:""
      },
      updatedAt:new Date().toISOString()
    };

    const documents=[];

    if(buildResume){
      $("#packProgress").textContent="Generating tailored résumé…";
      const resumeText=createResumeTextForJob(job,description);
      if(!resumeText)throw new Error("The tailored résumé could not be generated.");

      const resumeName=`Cernice_Robinson_${sanitizeFileName(job.title)}_Resume`;
      const resumeDocx=await createDocxBlob("Cernice Robinson, MS",resumeText);
      const resumePdf=createPdfBlob("Cernice Robinson, MS — Tailored Resume",resumeText);

      if(storeFiles){
        $("#packProgress").textContent="Storing résumé files…";
        const docxUpload=await uploadPrivateDocument(key,`${resumeName}.docx`,resumeDocx,"application/vnd.openxmlformats-officedocument.wordprocessingml.document");
        const pdfUpload=await uploadPrivateDocument(key,`${resumeName}.pdf`,resumePdf,"application/pdf");

        if(docxUpload.stored)documents.push({type:"resume_docx",label:"Resume DOCX",fileName:`${resumeName}.docx`,path:docxUpload.path});
        if(pdfUpload.stored)documents.push({type:"resume_pdf",label:"Resume PDF",fileName:`${resumeName}.pdf`,path:pdfUpload.path});
      }else{
        const url=URL.createObjectURL(resumeDocx);
        const anchor=document.createElement("a");
        anchor.href=url;
        anchor.download=`${resumeName}.docx`;
        anchor.click();
        URL.revokeObjectURL(url);
      }
    }

    if(buildCover){
      $("#packProgress").textContent="Generating cover letter…";
      const coverText=createCoverLetterText(job,description);
      const coverName=`Cernice_Robinson_${sanitizeFileName(job.title)}_Cover_Letter`;
      const coverDocx=await createDocxBlob("Cover Letter",coverText);
      const coverPdf=createPdfBlob("Cover Letter",coverText);

      if(storeFiles){
        $("#packProgress").textContent="Storing cover-letter files…";
        const docxUpload=await uploadPrivateDocument(key,`${coverName}.docx`,coverDocx,"application/vnd.openxmlformats-officedocument.wordprocessingml.document");
        const pdfUpload=await uploadPrivateDocument(key,`${coverName}.pdf`,coverPdf,"application/pdf");

        if(docxUpload.stored)documents.push({type:"cover_docx",label:"Cover Letter DOCX",fileName:`${coverName}.docx`,path:docxUpload.path});
        if(pdfUpload.stored)documents.push({type:"cover_pdf",label:"Cover Letter PDF",fileName:`${coverName}.pdf`,path:pdfUpload.path});
      }else{
        const url=URL.createObjectURL(coverDocx);
        const anchor=document.createElement("a");
        anchor.href=url;
        anchor.download=`${coverName}.docx`;
        anchor.click();
        URL.revokeObjectURL(url);
      }
    }

    savedArchive[key].documents=[
      ...savedArchive[key].documents.filter(existing=>!documents.some(next=>next.type===existing.type)),
      ...documents
    ];

    persist();
    if(cloudReady&&cloudUser)await pushCloudSnapshot();

    renderJobs();
    renderDashboard();
    renderSavedJobs();
    renderPipeline();

    $("#packProgress").textContent=markApplied
      ?"Application pack complete. Job marked Applied and synced."
      :"Application pack complete. Review and submit, then mark Applied.";
  }catch(error){
    console.error(error);
    $("#packProgress").textContent=`Error: ${error.message}`;
  }finally{
    $("#runApplicationPackBtn").disabled=false;
  }
}

$("#runApplicationPackBtn").onclick=runApplicationPack;

if($("#discoveryFilter"))$("#discoveryFilter").oninput=renderJobs;


async function renderSourceCoverage(){
  const wrap=$("#sourceCoverage");
  if(!wrap)return;

  try{
    const response=await fetch(`data/source_coverage.json?v=${Date.now()}`,{cache:"no-store"});
    const coverage=await response.json();

    const group=(title,items)=>`
      <div class="coverage-group">
        <h3>${title}</h3>
        <div class="coverage-items">
          ${(items||[]).map(item=>`
            <div class="coverage-item ${item.active?"coverage-active":"coverage-inactive"}">
              <strong>${item.name}</strong>
              <span>${item.active?"Active":"Not active"}${Number.isFinite(item.matches)?` · ${item.matches} matches`:""}</span>
              ${item.note?`<small>${item.note}</small>`:""}
            </div>`).join("")}
        </div>
      </div>`;

    wrap.innerHTML=
      group("Automated",coverage.automated_sources)+
      group("Configurable employer sources",coverage.configurable_sources)+
      group("Discovery-only—not scraped",coverage.discovery_only_sources);
  }catch(error){
    wrap.innerHTML='<p class="muted">Source coverage will appear after the next successful scan.</p>';
  }
}
