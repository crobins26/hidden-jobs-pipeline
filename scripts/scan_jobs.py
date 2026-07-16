#!/usr/bin/env python3
"""Career Intelligence Center v13 multi-source job scanner.

Primary broad source:
- Adzuna Jobs API

Optional supplemental source:
- TheirStack API, when credits are available

Direct employer / ATS verification layer:
- Greenhouse Job Board API
- Lever Postings API
- Ashby Job Board API
- SmartRecruiters public Posting API when configured in company_sources.csv

The scanner:
- uses a $130,000 salary floor when compensation is published;
- keeps strong-fit roles with unpublished compensation;
- limits the final feed to 100 unique jobs;
- favors remote US or Midwest-friendly roles;
- prefers direct employer and official ATS links;
- rejects obvious sales, engineering, product, legal, and unrelated jobs.
"""

from __future__ import annotations

import csv
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "jobs.json"
CONFIG = json.loads((DATA / "search_config.json").read_text(encoding="utf-8"))
PROFILE = json.loads((DATA / "candidate_profile.json").read_text(encoding="utf-8"))

MIN_SALARY = 130_000
MAX_DAILY_JOBS = 100
MAX_AGE_DAYS = int(CONFIG.get("max_age_days", 30))

MIDWEST_STATES = {
    "IL", "IN", "WI", "MI", "MN", "OH", "IA", "MO", "KS", "NE", "ND", "SD"
}
MIDWEST_NAMES = {
    "illinois", "indiana", "wisconsin", "michigan", "minnesota", "ohio",
    "iowa", "missouri", "kansas", "nebraska", "north dakota", "south dakota",
    "chicago", "indianapolis", "milwaukee", "detroit", "minneapolis",
    "cleveland", "columbus", "cincinnati", "st. louis", "kansas city"
}

TITLE_GROUPS = [
    [
        "Senior Customer Success Manager",
        "Senior Manager Customer Success",
        "Director Customer Success",
        "Director Client Success",
        "Director Customer Experience",
        "Director Customer Operations",
    ],
    [
        "Customer Success Operations Manager",
        "Senior Manager Customer Success Operations",
        "Enterprise Customer Success Manager",
        "Strategic Customer Success Manager",
        "Customer Success Enablement Manager",
        "Customer Success Programs Manager",
    ],
    [
        "Director Revenue Operations",
        "Director Commercial Operations",
        "Director Sales Operations",
        "Director Business Operations",
        "Director Operational Excellence",
        "Director Business Transformation",
    ],
    [
        "Strategy Operations Director",
        "Strategic Accounts Director",
        "Implementation Director",
        "Professional Services Director",
        "Senior Director Customer Success",
        "Head Customer Success",
    ],
]

PRIMARY_TITLES = [x.lower() for x in CONFIG.get("priority_titles", [])]
STRETCH_TITLES = [x.lower() for x in CONFIG.get("stretch_titles", [])]
EXCLUDED_TITLE_TERMS = [x.lower() for x in CONFIG.get("exclude_title_terms", [])]

DIRECT_HOST_MARKERS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "smartrecruiters.com",
    "myworkdayjobs.com",
    "workdayjobs.com",
    "icims.com",
    "jobvite.com",
    "teamtailor.com",
    "recruitee.com",
    "bamboohr.com",
    "successfactors.com",
    "oraclecloud.com",
)

AGGREGATOR_HOSTS = (
    "adzuna.com",
    "linkedin.com",
    "indeed.com",
    "ziprecruiter.com",
    "talent.com",
    "jooble.org",
    "glassdoor.com",
    "simplyhired.com",
)

def request_json(url: str, method: str = "GET", payload=None, headers=None):
    hdr = {
        "User-Agent": "CareerIntelligenceCenter/13.0",
        "Accept": "application/json",
    }
    if headers:
        hdr.update(headers)

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        hdr["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=hdr, method=method)
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))

def clean(value: str | None) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()

def parse_date(value) -> str | None:
    if not value:
        return None
    text = str(value)
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else None

def title_relevance(title: str):
    normalized = normalize_title(title)

    if any(normalize_title(term) in normalized for term in EXCLUDED_TITLE_TERMS):
        return None, 0

    if any(normalize_title(term) in normalized or normalized in normalize_title(term)
           for term in PRIMARY_TITLES):
        return "Priority Apply", 36

    if any(normalize_title(term) in normalized or normalized in normalize_title(term)
           for term in STRETCH_TITLES):
        return "Stretch", 18

    senior = any(marker in normalized for marker in (
        "director", "senior manager", "sr manager", "head", "lead"
    ))
    relevant = any(marker in normalized for marker in (
        "customer success", "client success", "customer experience",
        "customer operations", "revenue operations", "commercial operations",
        "sales operations", "business operations", "operational excellence",
        "business transformation", "strategic account", "implementation",
        "professional services", "enablement", "strategy operations"
    ))

    if senior and relevant:
        return "Strong Opportunity", 25

    return None, 0

def detect_track(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    tracks = [
        ("Customer Success", ["customer success", "client success", "renewal", "retention", "adoption"]),
        ("Customer Experience", ["customer experience", "customer operations"]),
        ("Revenue Operations", ["revenue operations", "revops"]),
        ("Commercial Operations", ["commercial operations", "commercial excellence", "pricing strategy"]),
        ("Sales Operations", ["sales operations"]),
        ("Business Transformation", ["business transformation", "operational excellence", "change management"]),
        ("Business Operations", ["business operations", "strategy and operations", "strategy & operations"]),
        ("Strategic Accounts", ["strategic account", "enterprise account", "customer growth"]),
        ("Implementation", ["implementation", "professional services"]),
        ("Enablement", ["enablement", "customer programs", "customer strategy"]),
    ]

    best = ("Leadership", 0)
    for track, terms in tracks:
        score = sum(text.count(term) for term in terms)
        if score > best[1]:
            best = (track, score)
    return best[0]

def valid_location(location: str, remote=False) -> str:
    location = location or ""
    upper = location.upper()
    lower = location.lower()

    if remote or "REMOTE" in upper or "UNITED STATES" in upper or upper.strip() in {"US", "USA"}:
        return "remote"

    if any(re.search(rf"\b{state}\b", upper) for state in MIDWEST_STATES):
        return "midwest"

    if any(name in lower for name in MIDWEST_NAMES):
        return "midwest"

    return "other"

def salary_info(raw_min=None, raw_max=None, raw_text="", currency="USD", period="year"):
    def to_number(value):
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number < 1000:
            number *= 1000
        return int(number)

    low = to_number(raw_min)
    high = to_number(raw_max)
    confidence = "high" if low and high and currency == "USD" else "medium"

    if low and high and high > low * 3:
        confidence = "low"

    if not low and not high:
        values = []
        patterns = [
            r"\$([1-9]\d{2}(?:,\d{3})?)\s*[kK]",
            r"\$([1-9]\d{1,2}(?:,\d{3})+)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, raw_text or ""):
                text = match.group(1).replace(",", "")
                number = int(text)
                if number < 1000:
                    number *= 1000
                if 70_000 <= number <= 700_000:
                    values.append(number)

        if values:
            low, high = min(values), max(values)
            confidence = "low" if high > low * 3 else "medium"

    return low, high, confidence

def profile_score(title, description, track, bucket, location_type, salary_max, posted_at):
    text = f"{title} {description}".lower()
    score = {
        "Priority Apply": 52,
        "Strong Opportunity": 42,
        "Stretch": 30,
    }.get(bucket, 25)

    hits = sum(1 for strength in PROFILE.get("strengths", []) if strength.lower() in text)
    score += min(24, hits * 2)

    if track in ("Customer Success", "Customer Experience"):
        score += 7

    if location_type == "remote":
        score += 6
    elif location_type == "midwest":
        score += 5

    if salary_max:
        if salary_max >= 180_000:
            score += 6
        elif salary_max >= 150_000:
            score += 4
        elif salary_max >= MIN_SALARY:
            score += 2

    age_days = 999
    if posted_at:
        try:
            posted = datetime.fromisoformat(str(posted_at).replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - posted.astimezone(timezone.utc)).days
        except ValueError:
            pass

    if age_days <= 3:
        score += 5
    elif age_days <= 7:
        score += 3

    if any(term in text for term in (
        "quota carrying", "new logo acquisition", "individual contributor sales"
    )):
        score -= 20

    if any(term in normalize_title(title) for term in (
        "product", "engineering", "developer", "technical architect"
    )):
        score -= 25

    return max(35, min(96, score)), age_days

def intelligence(score, track, bucket, description, age_days, salary_confidence):
    probability = "High" if score >= 86 else "Medium" if score >= 72 else "Low"
    application_time = 15 if score >= 86 else 25 if score >= 72 else 40
    resume = PROFILE.get("preferred_resume_by_track", {}).get(track, "Business Transformation")
    cover_letter = "Recommended" if bucket == "Stretch" or score < 82 else "Optional"
    freshness = (
        "New <72h" if age_days <= 3
        else "Recent" if age_days <= 7
        else "Aging" if age_days > 21
        else "Active"
    )

    risks = []
    text = description.lower()
    if "saas" in text or "software" in text:
        risks.append("May require deeper direct SaaS experience")
    if "global" in text:
        risks.append("Global scope may be a stretch")
    if salary_confidence == "low":
        risks.append("Salary range needs verification")

    return (
        probability,
        application_time,
        resume,
        cover_letter,
        freshness,
        "; ".join(risks[:2]) or "No major gap detected",
    )

def source_quality(url: str, source_name: str) -> int:
    host = urlparse(url or "").netloc.lower()

    if any(marker in host for marker in DIRECT_HOST_MARKERS):
        return 4
    if source_name in {"Greenhouse", "Lever", "Ashby", "SmartRecruiters"}:
        return 4
    if host and not any(marker in host for marker in AGGREGATOR_HOSTS):
        return 3
    if source_name == "Adzuna":
        return 1
    return 2

def normalize(
    company,
    title,
    location,
    description,
    url,
    posted=None,
    salary_min=None,
    salary_max=None,
    remote=False,
    source="",
    source_url=None,
):
    bucket, _ = title_relevance(title)
    if not bucket:
        return None

    location_type = valid_location(location, remote)
    if location_type == "other":
        return None

    low, high, salary_confidence = salary_info(
        salary_min, salary_max, description
    )

    if high and high < MIN_SALARY:
        return None

    track = detect_track(title, description)
    score, age_days = profile_score(
        title, description, track, bucket, location_type, high, posted
    )

    if score < 62:
        return None

    (
        interview_probability,
        application_time,
        recommended_resume,
        cover_letter,
        freshness,
        risk,
    ) = intelligence(
        score, track, bucket, description, age_days, salary_confidence
    )

    official_link = url or source_url or ""
    quality = source_quality(official_link, source)

    return {
        "id": re.sub(r"\W+", "-", f"{company}-{title}-{location}".lower()).strip("-"),
        "company": company,
        "title": title,
        "location": location or "Location not stated",
        "location_type": location_type,
        "track": track,
        "priority_bucket": bucket,
        "salary_min": low,
        "salary_max": high,
        "salary_period": "year",
        "salary_confidence": salary_confidence,
        "posted_at": posted or datetime.now(timezone.utc).date().isoformat(),
        "apply_url": official_link,
        "source_url": source_url or official_link,
        "source": source,
        "source_quality": quality,
        "fit_score": score,
        "interview_probability": interview_probability,
        "application_time_minutes": application_time,
        "recommended_resume": recommended_resume,
        "cover_letter": cover_letter,
        "freshness": freshness,
        "main_risk": risk,
        "job_description": description[:12_000],
        "reason": (
            f"Matches {track.lower()}, analytics, process improvement, "
            "enterprise stakeholder management, and leadership scope."
        ),
        "tags": ["Direct employer" if quality >= 3 else "Broad discovery", track, bucket, freshness],
    }

# ------------------------------------------------------------------
# Adzuna broad search
# ------------------------------------------------------------------
def scan_adzuna():
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()

    if not app_id or not app_key:
        return [], ["Adzuna credentials not configured; broad Adzuna search skipped."]

    jobs = []
    warnings = []

    query_groups = [
        "customer success director OR senior customer success manager OR client success director",
        "revenue operations director OR commercial operations director OR sales operations director",
        "business operations director OR business transformation director OR operational excellence director",
        "strategic accounts director OR implementation director OR professional services director",
    ]

    for group_number, query in enumerate(query_groups, 1):
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": 25,
            "what_or": query,
            "where": "United States",
            "sort_by": "date",
            "max_days_old": MAX_AGE_DAYS,
            "content-type": "application/json",
        }
        url = f"https://api.adzuna.com/v1/api/jobs/us/search/1?{urlencode(params)}"

        try:
            data = request_json(url)
        except HTTPError as error:
            warnings.append(f"Adzuna group {group_number} HTTP {error.code}; group skipped.")
            continue
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            warnings.append(f"Adzuna group {group_number} unavailable: {str(error)[:180]}")
            continue

        for item in data.get("results", []):
            redirect_url = item.get("redirect_url") or item.get("adref") or ""
            description = clean(item.get("description", ""))
            location = (
                item.get("location", {}).get("display_name")
                or item.get("location", {}).get("area", [""])[-1]
                or ""
            )
            company = item.get("company", {}).get("display_name") or "Unknown company"
            title = item.get("title", "")
            remote = "remote" in f"{title} {location} {description}".lower()

            job = normalize(
                company=company,
                title=title,
                location=location,
                description=description,
                url=redirect_url,
                posted=parse_date(item.get("created")),
                salary_min=item.get("salary_min"),
                salary_max=item.get("salary_max"),
                remote=remote,
                source="Adzuna",
                source_url=redirect_url,
            )
            if job:
                jobs.append(job)

        time.sleep(0.25)

    return jobs, warnings

# ------------------------------------------------------------------
# TheirStack optional supplemental search
# ------------------------------------------------------------------
def scan_theirstack():
    key = os.getenv("THEIRSTACK_API_KEY", "").strip()
    if not key:
        return [], ["TheirStack key not configured; supplemental search skipped."]

    jobs = []
    warnings = []

    for group_number, titles in enumerate(TITLE_GROUPS, 1):
        payload = {
            "job_title_or": titles,
            "job_country_code_or": ["US"],
            "posted_at_max_age_days": MAX_AGE_DAYS,
            "limit": 25,
        }

        try:
            data = request_json(
                "https://api.theirstack.com/v1/jobs/search",
                method="POST",
                payload=payload,
                headers={"Authorization": f"Bearer {key}"},
            )
        except HTTPError as error:
            detail = ""
            try:
                detail = error.read().decode("utf-8", "ignore")[:180]
            except Exception:
                pass
            warnings.append(
                f"TheirStack group {group_number} HTTP {error.code}; skipped. {detail}"
            )
            continue
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            warnings.append(
                f"TheirStack group {group_number} unavailable: {str(error)[:180]}"
            )
            continue

        rows = data.get("data") or data.get("jobs") or []
        for item in rows:
            url = item.get("final_url") or item.get("url") or item.get("job_url") or ""
            if not url:
                continue

            job = normalize(
                company=item.get("company_name") or item.get("company") or "Unknown company",
                title=item.get("job_title") or item.get("title") or "",
                location=item.get("location") or item.get("short_location") or "",
                description=clean(
                    item.get("description") or item.get("description_markdown") or ""
                ),
                url=url,
                posted=parse_date(item.get("date_posted") or item.get("posted_at")),
                salary_min=item.get("salary_min") or item.get("min_salary"),
                salary_max=item.get("salary_max") or item.get("max_salary"),
                remote=bool(item.get("remote") or item.get("is_remote")),
                source="TheirStack",
            )
            if job:
                jobs.append(job)

        time.sleep(0.35)

    return jobs, warnings

# ------------------------------------------------------------------
# Direct ATS scanners
# ------------------------------------------------------------------
def scan_greenhouse(company, slug):
    data = request_json(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    )
    output = []
    for item in data.get("jobs", []):
        output.append(normalize(
            company=company,
            title=item.get("title", ""),
            location=item.get("location", {}).get("name", ""),
            description=clean(item.get("content", "")),
            url=item.get("absolute_url", ""),
            posted=parse_date(item.get("updated_at")),
            source="Greenhouse",
        ))
    return output

def scan_lever(company, slug):
    data = request_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    output = []
    for item in data:
        description = clean(
            f"{item.get('descriptionPlain', '')} {item.get('additionalPlain', '')}"
        )
        output.append(normalize(
            company=company,
            title=item.get("text", ""),
            location=item.get("categories", {}).get("location", ""),
            description=description,
            url=item.get("hostedUrl", ""),
            source="Lever",
        ))
    return output

def scan_ashby(company, slug):
    data = request_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    )
    output = []

    for item in data.get("jobs", []):
        compensation = item.get("compensation") or {}
        values = [
            int(value) for value in re.findall(
                r'"(?:minValue|maxValue|value)"\s*:\s*(\d+)',
                json.dumps(compensation),
            )
        ]
        values = [value for value in values if 70_000 <= value <= 700_000]

        output.append(normalize(
            company=company,
            title=item.get("title", ""),
            location=item.get("location", ""),
            description=clean(item.get("descriptionPlain", "")),
            url=item.get("jobUrl") or item.get("applyUrl", ""),
            posted=parse_date(item.get("publishedAt")),
            salary_min=min(values) if values else None,
            salary_max=max(values) if values else None,
            source="Ashby",
        ))

    return output

def scan_smartrecruiters(company, slug):
    # Public Posting API is company-scoped.
    data = request_json(
        f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100"
    )
    output = []

    for item in data.get("content", []):
        posting_id = item.get("id")
        details = item
        if posting_id:
            try:
                details = request_json(
                    f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{posting_id}"
                )
            except Exception:
                details = item

        location_obj = details.get("location") or item.get("location") or {}
        location = ", ".join(filter(None, [
            location_obj.get("city"),
            location_obj.get("region"),
            location_obj.get("country"),
        ]))

        output.append(normalize(
            company=company,
            title=details.get("name") or item.get("name") or "",
            location=location,
            description=clean(details.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", "")),
            url=details.get("applyUrl") or details.get("ref") or "",
            posted=parse_date(details.get("releasedDate") or item.get("releasedDate")),
            remote="remote" in f"{location} {details.get('name', '')}".lower(),
            source="SmartRecruiters",
        ))

    return output

def scan_direct_ats():
    source_file = DATA / "company_sources.csv"
    if not source_file.exists():
        return [], ["company_sources.csv is missing."]

    jobs = []
    warnings = []

    with source_file.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    scanners = {
        "greenhouse": scan_greenhouse,
        "lever": scan_lever,
        "ashby": scan_ashby,
        "smartrecruiters": scan_smartrecruiters,
    }

    for row in rows:
        if row.get("enabled", "yes").lower() != "yes":
            continue

        ats = row.get("ats", "").strip().lower()
        scanner = scanners.get(ats)
        if not scanner:
            continue

        company = row.get("company", "").strip()
        slug = row.get("slug", "").strip()

        try:
            jobs.extend(job for job in scanner(company, slug) if job)
        except Exception as error:
            warnings.append(f"{company}: {str(error)[:160]}")

        time.sleep(0.08)

    return jobs, warnings

def canonical_key(job):
    title = normalize_title(job.get("title", ""))
    company = normalize_title(job.get("company", ""))
    location = normalize_title(job.get("location", ""))
    return f"{company}|{title}|{location}"

def merge_jobs(existing, candidate):
    # Prefer official ATS or direct company links over aggregator redirects.
    if candidate.get("source_quality", 0) > existing.get("source_quality", 0):
        better, other = candidate, existing
    elif candidate.get("fit_score", 0) > existing.get("fit_score", 0):
        better, other = candidate, existing
    else:
        better, other = existing, candidate

    merged = dict(other)
    merged.update({key: value for key, value in better.items() if value not in (None, "", [])})

    if not merged.get("job_description"):
        merged["job_description"] = other.get("job_description", "")

    sources = set(existing.get("sources", [existing.get("source")]))
    sources.update(candidate.get("sources", [candidate.get("source")]))
    merged["sources"] = sorted(source for source in sources if source)

    return merged

def main():
    adzuna_jobs, adzuna_warnings = scan_adzuna()
    their_jobs, their_warnings = scan_theirstack()
    direct_jobs, direct_warnings = scan_direct_ats()

    all_jobs = adzuna_jobs + their_jobs + direct_jobs

    unique = {}
    for job in all_jobs:
        if not job or not job.get("apply_url"):
            continue

        key = canonical_key(job)
        if key in unique:
            unique[key] = merge_jobs(unique[key], job)
        else:
            job["sources"] = [job.get("source")]
            unique[key] = job

    ranked = list(unique.values())
    ranked.sort(
        key=lambda job: (
            job.get("fit_score", 0),
            job.get("source_quality", 0),
            1 if job.get("freshness") == "New <72h" else 0,
            job.get("salary_max") or 0,
            job.get("posted_at") or "",
        ),
        reverse=True,
    )

    discovered_count = len(ranked)
    jobs = ranked[:MAX_DAILY_JOBS]

    for index, job in enumerate(jobs):
        job["top_10_today"] = index < 10
        if index < 10 and "Top 10 Today" not in job["tags"]:
            job["tags"].append("Top 10 Today")

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "minimum_salary": MIN_SALARY,
        "daily_job_cap": MAX_DAILY_JOBS,
        "broad_search_enabled": bool(adzuna_jobs or their_jobs),
        "provider_status": {
            "adzuna": {
                "active": bool(adzuna_jobs),
                "matches": len(adzuna_jobs),
            },
            "theirstack": {
                "active": bool(their_jobs),
                "matches": len(their_jobs),
            },
            "direct_ats": {
                "active": True,
                "matches": len(direct_jobs),
            },
        },
        "jobs": jobs,
        "match_count": len(jobs),
        "discovered_before_cap": discovered_count,
        "errors": (
            adzuna_warnings + their_warnings + direct_warnings
        )[:120],
    }

    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(
        f"Published {len(jobs)} jobs from {discovered_count} qualified unique matches. "
        f"Adzuna: {len(adzuna_jobs)}. TheirStack: {len(their_jobs)}. "
        f"Direct ATS: {len(direct_jobs)}. Salary floor: ${MIN_SALARY:,}."
    )

if __name__ == "__main__":
    main()
