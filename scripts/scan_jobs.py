#!/usr/bin/env python3
"""Fetch public jobs from Greenhouse, Lever, and Ashby boards and rank them."""
from __future__ import annotations
import csv, json, re, time, html
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/"data/company_sources.csv"
OUT=ROOT/"data/jobs.json"
TARGETS=["customer success","client success","customer experience","revenue operations","commercial operations","business operations","sales operations","operational excellence","business transformation","strategy and operations","strategic accounts","account management","implementation","enablement"]
SENIOR=["director","senior director","head of","vice president","vp ","group manager","senior manager"]
MIDWEST=["illinois","indiana","chicago","wisconsin","michigan","minnesota","ohio","iowa","missouri","kansas","nebraska","north dakota","south dakota","midwest"]
def get(url):
    req=Request(url,headers={"User-Agent":"HiddenJobsPipeline/1.0"})
    with urlopen(req,timeout=25) as r:return json.loads(r.read().decode())
def clean(s):return re.sub(r"\s+"," ",re.sub("<[^>]+>"," ",html.unescape(s or ""))).strip()
def salary(text):
    vals=[]
    for x in re.findall(r"\$([1-9]\d{2}(?:,\d{3})+|[1-9]\d{2})\s*[kK]?",text or ""):
        n=int(x.replace(",","")); vals.append(n*1000 if n<1000 else n)
    vals=[v for v in vals if 70000<=v<=700000]
    return (min(vals),max(vals)) if vals else (None,None)
def classify(title,desc,location):
    t=f"{title} {desc}".lower(); track=next((x.title() for x in TARGETS if x in t),"Leadership")
    remote="remote" in (location or "").lower() or "remote" in t[:1200]
    midwest=any(x in (location or "").lower() for x in MIDWEST)
    loc_type="remote" if remote else "midwest" if midwest else "other"
    score=45+25*any(x in title.lower() for x in SENIOR)+18*any(x in t for x in TARGETS)+8*remote+5*midwest
    if "healthcare" in t or "saas" in t or "enterprise" in t:score+=4
    return track,loc_type,min(score,99)
def normalize(company,title,location,desc,url,posted=None,comp=None):
    lo,hi=comp or salary(desc);track,lt,score=classify(title,desc,location)
    if not any(x in title.lower() for x in SENIOR):return None
    if not any(x in f"{title} {desc}".lower() for x in TARGETS):return None
    if lt=="other":return None
    if hi and hi<150000:return None
    reason=f"Strong alignment with {track.lower()}, senior leadership, analytics, process improvement, and enterprise stakeholder management."
    return {"id":re.sub(r"\W+","-",f"{company}-{title}-{location}".lower()),"company":company,"title":title,"location":location,"location_type":lt,"track":track,"salary_min":lo,"salary_max":hi,"salary_period":"year","posted_at":posted or datetime.now(timezone.utc).date().isoformat(),"apply_url":url,"fit_score":score,"reason":reason,"tags":["Direct employer","Company career site",track]}
def greenhouse(name,slug):
    d=get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    return [normalize(name,j["title"],j.get("location",{}).get("name",""),clean(j.get("content","")),j.get("absolute_url",""),j.get("updated_at","")[:10]) for j in d.get("jobs",[])]
def lever(name,slug):
    d=get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    out=[]
    for j in d:
        cats=j.get("categories",{});desc=" ".join([j.get("descriptionPlain",""),j.get("additionalPlain","")])
        out.append(normalize(name,j["text"],cats.get("location",""),desc,j.get("hostedUrl","")))
    return out
def ashby(name,slug):
    d=get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    out=[]
    for j in d.get("jobs",[]):
        c=j.get("compensation") or {}; comp=None
        txt=json.dumps(c)
        vals=[int(x) for x in re.findall(r'"(?:minValue|maxValue|value)"\s*:\s*(\d+)',txt)]
        if vals:comp=(min(vals),max(vals))
        out.append(normalize(name,j["title"],j.get("location",""),clean(j.get("descriptionPlain","")),j.get("jobUrl") or j.get("applyUrl",""),j.get("publishedAt","")[:10],comp))
    return out
def main():
    jobs=[]; errors=[]
    with SOURCES.open() as f:
        for row in csv.DictReader(f):
            if row.get("enabled","yes").lower()!="yes":continue
            try:
                fn={"greenhouse":greenhouse,"lever":lever,"ashby":ashby}[row["ats"].lower()]
                jobs.extend(x for x in fn(row["company"],row["slug"]) if x)
            except (HTTPError,URLError,TimeoutError,KeyError,ValueError) as e:errors.append({"company":row["company"],"error":str(e)[:160]})
            time.sleep(.12)
    unique={j["apply_url"]:j for j in jobs if j and j["apply_url"]}
    payload={"updated_at":datetime.now(timezone.utc).isoformat(),"jobs":sorted(unique.values(),key=lambda x:(x["fit_score"],x.get("salary_max") or 0),reverse=True),"source_count":sum(1 for _ in csv.DictReader(SOURCES.open())),"errors":errors[:50]}
    OUT.write_text(json.dumps(payload,indent=2))
    print(f"Wrote {len(unique)} matching jobs from {payload['source_count']} configured company boards.")
if __name__=="__main__":main()
