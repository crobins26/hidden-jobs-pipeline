#!/usr/bin/env python3
from __future__ import annotations

import csv, html, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "jobs.json"
CONFIG = json.loads((DATA/"search_config.json").read_text())
PROFILE = json.loads((DATA/"candidate_profile.json").read_text())
MIN_SALARY = int(CONFIG["minimum_salary"])

def request_json(url, method="GET", payload=None, headers=None):
    hdr={"User-Agent":"CareerIntelligenceCenter/7.0","Accept":"application/json"}
    if headers: hdr.update(headers)
    data=None
    if payload is not None:
        data=json.dumps(payload).encode()
        hdr["Content-Type"]="application/json"
    req=Request(url,data=data,headers=hdr,method=method)
    with urlopen(req,timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))

def clean(s):
    return re.sub(r"\s+"," ",re.sub("<[^>]+>"," ",html.unescape(s or ""))).strip()

def norm_title(s):
    return re.sub(r"[^a-z0-9]+"," ",(s or "").lower()).strip()

def title_relevance(title):
    t=norm_title(title)
    if any(norm_title(x) in t for x in CONFIG["exclude_title_terms"]):
        return None,0
    primary=[norm_title(x) for x in CONFIG["priority_titles"]]
    stretch=[norm_title(x) for x in CONFIG["stretch_titles"]]
    if any(x in t or t in x for x in primary):
        return "Priority Apply",36
    if any(x in t or t in x for x in stretch):
        return "Stretch",18
    senior=any(x in t for x in ["director","senior manager","sr manager","lead"])
    domain=any(x in t for x in [
        "customer success","client success","customer experience","customer operations",
        "revenue operations","commercial operations","sales operations","business operations",
        "operational excellence","business transformation","strategic account",
        "implementation","professional services","enablement"
    ])
    return ("Strong Opportunity",25) if senior and domain else (None,0)

def detect_track(title,desc):
    text=f"{title} {desc}".lower()
    tracks=[
      ("Customer Success",["customer success","client success","renewal","retention","adoption"]),
      ("Customer Experience",["customer experience","customer operations"]),
      ("Revenue Operations",["revenue operations","revops"]),
      ("Commercial Operations",["commercial operations","commercial excellence"]),
      ("Sales Operations",["sales operations"]),
      ("Business Transformation",["business transformation","operational excellence","change management"]),
      ("Business Operations",["business operations","strategy and operations","strategy & operations"]),
      ("Strategic Accounts",["strategic account","enterprise account","customer growth"]),
      ("Implementation",["implementation","professional services"]),
      ("Enablement",["enablement","customer programs","customer strategy"])
    ]
    best=("Leadership",0)
    for track,terms in tracks:
        score=sum(text.count(x) for x in terms)
        if score>best[1]: best=(track,score)
    return best[0]

def valid_location(location,remote=False):
    loc=(location or "").upper()
    if remote or "REMOTE" in loc or "UNITED STATES" in loc or loc.strip() in {"US","USA"}:
        return "remote"
    if any(re.search(rf"\b{state}\b",loc) for state in CONFIG["midwest_states"]):
        return "midwest"
    if any(x in loc.lower() for x in ["illinois","indiana","wisconsin","michigan","minnesota","ohio","iowa","missouri","kansas","nebraska","dakota","chicago"]):
        return "midwest"
    return "other"

def salary_info(raw_min=None,raw_max=None,raw_text="",currency="USD",period="year"):
    try: lo=int(float(raw_min)) if raw_min not in (None,"") else None
    except: lo=None
    try: hi=int(float(raw_max)) if raw_max not in (None,"") else None
    except: hi=None
    confidence="high" if lo and hi and currency=="USD" and period.lower() in ("year","yearly","annual") else "medium"
    if lo and hi and hi>lo*3:
        confidence="low"
    if not lo and not hi:
        vals=[]
        for m in re.finditer(r"\$([1-9]\d{2}(?:,\d{3})?|[1-9]\d{1,2},\d{3})\s*[kK]?",raw_text or ""):
            n=int(m.group(1).replace(",",""))
            if n<1000:n*=1000
            if 70000<=n<=700000:vals.append(n)
        if vals:
            lo,hi=min(vals),max(vals)
            confidence="low" if hi>lo*3 else "medium"
    return lo,hi,confidence

def profile_score(title,desc,track,bucket,loc_type,salary_max,posted):
    text=f"{title} {desc}".lower()
    score={"Priority Apply":52,"Strong Opportunity":42,"Stretch":30}.get(bucket,25)
    strengths=PROFILE["strengths"]
    hits=sum(1 for x in strengths if x in text)
    score+=min(24,hits*2)
    if track in ("Customer Success","Customer Experience"):score+=7
    if loc_type=="remote":score+=6
    elif loc_type=="midwest":score+=5
    if salary_max:
        score+=6 if salary_max>=180000 else 4 if salary_max>=150000 else 2
    age=999
    if posted:
        try:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(str(posted).replace("Z","+00:00")).astimezone(timezone.utc)).days
        except: pass
    if age<=3:score+=5
    elif age<=7:score+=3
    # Hard penalties for domain gaps
    if any(x in text for x in ["quota carrying","new logo acquisition","individual contributor sales"]):score-=20
    if any(x in norm_title(title) for x in ["product","engineering","developer","technical architect"]):score-=25
    return max(35,min(96,score)),age

def intelligence(score,track,bucket,desc,age,salary_conf):
    if score>=86: probability="High"
    elif score>=72: probability="Medium"
    else: probability="Low"
    app_time=15 if score>=86 else 25 if score>=72 else 40
    resume=PROFILE["preferred_resume_by_track"].get(track,"Business Transformation")
    cover = "Recommended" if bucket=="Stretch" or score<82 else "Optional"
    freshness="New <72h" if age<=3 else "Recent" if age<=7 else "Aging" if age>21 else "Active"
    risk=[]
    text=desc.lower()
    if "saas" in text or "software" in text:risk.append("May require deeper direct SaaS experience")
    if "global" in text:risk.append("Global scope may be a stretch")
    if salary_conf=="low":risk.append("Salary range needs verification")
    return probability,app_time,resume,cover,freshness,"; ".join(risk[:2]) or "No major gap detected"

def normalize(company,title,location,desc,url,posted=None,smin=None,smax=None,remote=False,source=""):
    bucket,base=title_relevance(title)
    if not bucket:return None
    loc_type=valid_location(location,remote)
    if loc_type=="other":return None
    lo,hi,sconf=salary_info(smin,smax,desc)
    if hi and hi<MIN_SALARY:return None
    track=detect_track(title,desc)
    score,age=profile_score(title,desc,track,bucket,loc_type,hi,posted)
    if score<62:return None
    prob,app_time,resume,cover,freshness,risk=intelligence(score,track,bucket,desc,age,sconf)
    return {
      "id":re.sub(r"\W+","-",f"{company}-{title}-{location}".lower()).strip("-"),
      "company":company,"title":title,"location":location or "Location not stated",
      "location_type":loc_type,"track":track,"priority_bucket":bucket,
      "salary_min":lo,"salary_max":hi,"salary_period":"year",
      "salary_confidence":sconf,"posted_at":posted or datetime.now(timezone.utc).date().isoformat(),
      "apply_url":url,"fit_score":score,"interview_probability":prob,
      "application_time_minutes":app_time,"recommended_resume":resume,
      "cover_letter":cover,"freshness":freshness,"main_risk":risk,
      "source":source,"reason":f"Matches {track.lower()}, analytics, process improvement, enterprise stakeholder management, and leadership scope.",
      "tags":["Direct employer",track,bucket,freshness]
    }

def scan_theirstack():
    key=os.getenv("THEIRSTACK_API_KEY","").strip()
    if not key:return [],["THEIRSTACK_API_KEY not configured; broad multi-ATS search skipped."]
    titles=CONFIG["priority_titles"]+CONFIG["stretch_titles"]
    payload={
      "job_title_or":titles,
      "job_country_code_or":["US"],
      "posted_at_max_age_days":CONFIG["max_age_days"],
      "limit":CONFIG["daily_result_limit"]
    }
    data=request_json("https://api.theirstack.com/v1/jobs/search","POST",payload,{
      "Authorization":f"Bearer {key}"
    })
    rows=data.get("data") or data.get("jobs") or []
    jobs=[]
    for j in rows:
        url=j.get("final_url") or j.get("url") or j.get("job_url") or ""
        if not url:continue
        jobs.append(normalize(
          j.get("company_name") or j.get("company") or "Unknown",
          j.get("job_title") or j.get("title") or "",
          j.get("location") or j.get("short_location") or "",
          clean(j.get("description") or j.get("description_markdown") or ""),
          url,
          j.get("date_posted") or j.get("posted_at"),
          j.get("salary_min") or j.get("min_salary"),
          j.get("salary_max") or j.get("max_salary"),
          bool(j.get("remote") or j.get("is_remote")),
          "TheirStack broad search"
        ))
    return [x for x in jobs if x],[]

def greenhouse(company,slug):
    d=request_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    return [normalize(company,j.get("title",""),j.get("location",{}).get("name",""),
      clean(j.get("content","")),j.get("absolute_url",""),(j.get("updated_at") or "")[:10],
      source="Greenhouse") for j in d.get("jobs",[])]

def lever(company,slug):
    d=request_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    out=[]
    for j in d:
        out.append(normalize(company,j.get("text",""),j.get("categories",{}).get("location",""),
          clean(j.get("descriptionPlain","")+" "+j.get("additionalPlain","")),j.get("hostedUrl",""),
          source="Lever"))
    return out

def ashby(company,slug):
    d=request_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    out=[]
    for j in d.get("jobs",[]):
        comp=j.get("compensation") or {}
        vals=[int(x) for x in re.findall(r'"(?:minValue|maxValue|value)"\s*:\s*(\d+)',json.dumps(comp))]
        vals=[v for v in vals if 70000<=v<=700000]
        out.append(normalize(company,j.get("title",""),j.get("location",""),
          clean(j.get("descriptionPlain","")),j.get("jobUrl") or j.get("applyUrl",""),
          (j.get("publishedAt") or "")[:10],min(vals) if vals else None,max(vals) if vals else None,
          source="Ashby"))
    return out

def scan_fallback():
    jobs=[];errors=[]
    source_file=DATA/"company_sources.csv"
    if not source_file.exists():return jobs,["company_sources.csv missing"]
    with source_file.open(encoding="utf-8-sig") as f: rows=list(csv.DictReader(f))
    for row in rows:
        if row.get("enabled","yes").lower()!="yes":continue
        try:
            fn={"greenhouse":greenhouse,"lever":lever,"ashby":ashby}.get(row["ats"].lower())
            if not fn:continue
            jobs.extend(x for x in fn(row["company"],row["slug"]) if x)
        except Exception as e:
            errors.append(f'{row.get("company")}: {str(e)[:120]}')
        time.sleep(.08)
    return jobs,errors

def main():
    broad,broad_errors=scan_theirstack()
    fallback,fallback_errors=scan_fallback()
    all_jobs=broad+fallback
    unique={}
    for j in all_jobs:
        if not j or not j.get("apply_url"):continue
        key=re.sub(r"[?#].*$","",j["apply_url"]).rstrip("/")
        if key not in unique or j["fit_score"]>unique[key]["fit_score"]:unique[key]=j
    jobs=list(unique.values())
    jobs.sort(key=lambda j:(j["fit_score"],j.get("salary_max") or 0,j.get("posted_at") or ""),reverse=True)
    for i,j in enumerate(jobs):
        j["top_10_today"]=i<10
        if i<10:j["tags"].append("Top 10 Today")
    payload={
      "updated_at":datetime.now(timezone.utc).isoformat(),
      "minimum_salary":MIN_SALARY,
      "broad_search_enabled":bool(os.getenv("THEIRSTACK_API_KEY","").strip()),
      "jobs":jobs,
      "match_count":len(jobs),
      "errors":(broad_errors+fallback_errors)[:100]
    }
    OUT.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print(f"Wrote {len(jobs)} jobs. Broad search enabled: {payload['broad_search_enabled']}.")
if __name__=="__main__":main()
