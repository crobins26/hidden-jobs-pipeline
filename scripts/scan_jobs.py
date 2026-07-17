#!/usr/bin/env python3
"""Career Intelligence Center v14 — multi-source career intelligence engine.

Automated broad discovery
-------------------------
- Adzuna API, when configured
- TheirStack API, when credits are available

Automated public ATS / employer connectors
-------------------------------------------
- Greenhouse
- Lever
- Ashby
- SmartRecruiters
- Workday CXS career sites
- Recruitee public careers API
- Personio public XML feeds
- Generic employer career pages exposing JSON-LD JobPosting
- Generic XML sitemaps containing JobPosting pages

Configurable / conditional connectors
--------------------------------------
- BambooHR, Teamtailor, Jobvite, iCIMS, Oracle Recruiting, and
  SAP SuccessFactors can be scanned through generic JSON-LD or sitemap
  connectors when their public career URLs are entered in career_sources.csv.
  Their implementations differ by employer and do not have one universal,
  anonymous public endpoint.

Discovery-only sources
----------------------
- Built In
- Wellfound
- Welcome to the Jungle

Those sites remain listed in source coverage but are not scraped. Their terms,
authentication, and dynamic pages are not treated as stable public APIs.
Adzuna may surface postings originating from them.

The engine also:
- publishes at most 100 jobs;
- prefers new discoveries over repeatedly shown roles;
- limits any one company to three current-feed roles;
- validates application links;
- removes expired or dead links;
- preserves a seen-jobs history;
- labels New Today, Previously Seen, and Still Active;
- prefers official ATS / employer links over aggregator redirects.
"""

from __future__ import annotations

import csv
import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

OUT = DATA / "jobs.json"
HISTORY_FILE = DATA / "seen_jobs.json"
ATS_FILE = DATA / "company_sources.csv"
CAREER_SOURCE_FILE = DATA / "career_sources.csv"
COVERAGE_FILE = DATA / "source_coverage.json"

CONFIG = json.loads((DATA / "search_config.json").read_text(encoding="utf-8"))
PROFILE = json.loads((DATA / "candidate_profile.json").read_text(encoding="utf-8"))

MIN_SALARY = 130_000
MAX_DAILY_JOBS = 100
MAX_PER_COMPANY = 3
MAX_AGE_DAYS = int(CONFIG.get("max_age_days", 30))
MAX_GENERIC_PAGES_PER_SOURCE = 80

MIDWEST_STATES = {
    "IL", "IN", "WI", "MI", "MN", "OH", "IA", "MO", "KS", "NE", "ND", "SD"
}
MIDWEST_NAMES = {
    "illinois", "indiana", "wisconsin", "michigan", "minnesota", "ohio",
    "iowa", "missouri", "kansas", "nebraska", "north dakota", "south dakota",
    "chicago", "indianapolis", "milwaukee", "detroit", "minneapolis",
    "cleveland", "columbus", "cincinnati", "st. louis", "kansas city"
}

DIRECT_HOST_MARKERS = (
    "greenhouse.io", "lever.co", "ashbyhq.com", "smartrecruiters.com",
    "myworkdayjobs.com", "workdayjobs.com", "icims.com", "jobvite.com",
    "teamtailor.com", "recruitee.com", "bamboohr.com", "personio.",
    "successfactors.", "oraclecloud.com",
)

AGGREGATOR_HOSTS = (
    "adzuna.com", "linkedin.com", "indeed.com", "ziprecruiter.com",
    "talent.com", "jooble.org", "glassdoor.com", "simplyhired.com",
)

EXPIRED_MARKERS = (
    "job is no longer available", "position has been filled",
    "job has expired", "this job is closed", "posting is no longer active",
    "no longer accepting applications", "page not found", "404 not found",
)

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

PRIMARY_TITLES = [str(x).lower() for x in CONFIG.get("priority_titles", [])]
STRETCH_TITLES = [str(x).lower() for x in CONFIG.get("stretch_titles", [])]
EXCLUDED_TITLE_TERMS = [
    str(x).lower() for x in CONFIG.get("exclude_title_terms", [])
]


def request_bytes(url, method="GET", payload=None, headers=None, timeout=35):
    request_headers = {
        "User-Agent": "CareerIntelligenceCenter/14.0",
        "Accept": "application/json,text/html,application/xml,text/xml;q=0.9,*/*;q=0.8",
    }
    if headers:
        request_headers.update(headers)

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", ""), response.geturl()


def request_json(url, method="GET", payload=None, headers=None):
    raw, _, _ = request_bytes(url, method, payload, headers)
    return json.loads(raw.decode("utf-8"))


def request_text(url):
    raw, _, final_url = request_bytes(url)
    return raw.decode("utf-8", "ignore"), final_url


def clean(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def parse_date(value):
    if not value:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", str(value))
    return match.group(0) if match else None


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def load_history():
    if not HISTORY_FILE.exists():
        return {}
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def save_history(history):
    HISTORY_FILE.write_text(
        json.dumps(history, indent=2),
        encoding="utf-8",
    )


def title_relevance(title):
    normalized = normalize_title(title)

    if any(normalize_title(term) in normalized for term in EXCLUDED_TITLE_TERMS):
        return None

    if any(
        normalize_title(term) in normalized or normalized in normalize_title(term)
        for term in PRIMARY_TITLES
    ):
        return "Priority Apply"

    if any(
        normalize_title(term) in normalized or normalized in normalize_title(term)
        for term in STRETCH_TITLES
    ):
        return "Stretch"

    senior = any(
        marker in normalized
        for marker in ("director", "senior manager", "sr manager", "head", "lead")
    )
    relevant = any(
        marker in normalized
        for marker in (
            "customer success", "client success", "customer experience",
            "customer operations", "revenue operations", "commercial operations",
            "sales operations", "business operations", "operational excellence",
            "business transformation", "strategic account", "implementation",
            "professional services", "enablement", "strategy operations",
            "account management operations",
        )
    )

    return "Strong Opportunity" if senior and relevant else None


def detect_track(title, description):
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

    best_track = "Leadership"
    best_score = 0
    for track, terms in tracks:
        score = sum(text.count(term) for term in terms)
        if score > best_score:
            best_track = track
            best_score = score
    return best_track


def location_type(location, remote=False):
    location = str(location or "")
    upper = location.upper()
    lower = location.lower()

    if (
        remote
        or "REMOTE" in upper
        or "UNITED STATES" in upper
        or upper.strip() in {"US", "USA"}
    ):
        return "remote"

    if any(re.search(rf"\b{state}\b", upper) for state in MIDWEST_STATES):
        return "midwest"

    if any(name in lower for name in MIDWEST_NAMES):
        return "midwest"

    return "other"


def salary_info(raw_min=None, raw_max=None, description=""):
    def number(value):
        if value in (None, ""):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed < 1000:
            parsed *= 1000
        return int(parsed)

    low = number(raw_min)
    high = number(raw_max)
    confidence = "high" if low and high else "medium"

    if low and high and high > low * 3:
        confidence = "low"

    if not low and not high:
        values = []
        patterns = [
            r"\$([1-9]\d{2})\s*[kK]",
            r"\$([1-9]\d{1,2}(?:,\d{3})+)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, description or ""):
                parsed = int(match.group(1).replace(",", ""))
                if parsed < 1000:
                    parsed *= 1000
                if 70_000 <= parsed <= 700_000:
                    values.append(parsed)

        if values:
            low, high = min(values), max(values)
            confidence = "low" if high > low * 3 else "medium"

    return low, high, confidence


def job_age_days(posted_at):
    if not posted_at:
        return 999
    try:
        posted = datetime.fromisoformat(str(posted_at).replace("Z", "+00:00"))
        return (
            datetime.now(timezone.utc) - posted.astimezone(timezone.utc)
        ).days
    except ValueError:
        return 999


def profile_score(title, description, track, bucket, loc_type, salary_max, posted_at):
    text = f"{title} {description}".lower()
    score = {
        "Priority Apply": 52,
        "Strong Opportunity": 42,
        "Stretch": 30,
    }.get(bucket, 25)

    hits = sum(
        1
        for strength in PROFILE.get("strengths", [])
        if str(strength).lower() in text
    )
    score += min(24, hits * 2)

    if track in ("Customer Success", "Customer Experience"):
        score += 7

    if loc_type == "remote":
        score += 6
    elif loc_type == "midwest":
        score += 5

    if salary_max:
        if salary_max >= 180_000:
            score += 6
        elif salary_max >= 150_000:
            score += 4
        elif salary_max >= MIN_SALARY:
            score += 2

    age = job_age_days(posted_at)
    if age <= 3:
        score += 5
    elif age <= 7:
        score += 3

    if any(
        phrase in text
        for phrase in (
            "quota carrying",
            "new logo acquisition",
            "individual contributor sales",
            "commission only",
        )
    ):
        score -= 22

    normalized = normalize_title(title)
    if any(
        term in normalized
        for term in (
            "software engineer", "developer", "technical architect",
            "product manager", "product director", "legal counsel",
        )
    ):
        score -= 30

    return max(35, min(96, score))


def source_quality(url, source):
    host = urlparse(url or "").netloc.lower()

    if any(marker in host for marker in DIRECT_HOST_MARKERS):
        return 5
    if source in {
        "Greenhouse", "Lever", "Ashby", "SmartRecruiters", "Workday",
        "Recruitee", "Personio", "Employer JSON-LD", "Employer Sitemap",
    }:
        return 5
    if host and not any(marker in host for marker in AGGREGATOR_HOSTS):
        return 4
    if source in {"Adzuna", "TheirStack"}:
        return 2
    return 3


def canonical_key(company, title, location):
    return "|".join(
        (
            normalize_title(company),
            normalize_title(title),
            normalize_title(location),
        )
    )


def normalize_job(
    company,
    title,
    location,
    description,
    apply_url,
    source,
    posted_at=None,
    salary_min=None,
    salary_max=None,
    remote=False,
    source_url=None,
):
    bucket = title_relevance(title)
    if not bucket:
        return None

    loc_type = location_type(location, remote)
    if loc_type == "other":
        return None

    low, high, salary_confidence = salary_info(
        salary_min,
        salary_max,
        description,
    )

    if high and high < MIN_SALARY:
        return None

    track = detect_track(title, description)
    fit_score = profile_score(
        title,
        description,
        track,
        bucket,
        loc_type,
        high,
        posted_at,
    )

    if fit_score < 62:
        return None

    age = job_age_days(posted_at)
    freshness = (
        "New <72h"
        if age <= 3
        else "Recent"
        if age <= 7
        else "Aging"
        if age > 21
        else "Active"
    )
    interview_probability = (
        "High"
        if fit_score >= 86
        else "Medium"
        if fit_score >= 72
        else "Low"
    )
    application_time = 15 if fit_score >= 86 else 25 if fit_score >= 72 else 40
    recommended_resume = PROFILE.get(
        "preferred_resume_by_track",
        {},
    ).get(track, "Business Transformation")
    cover_letter = "Recommended" if bucket == "Stretch" or fit_score < 82 else "Optional"

    risks = []
    lower_description = description.lower()
    if "saas" in lower_description or "software" in lower_description:
        risks.append("May require deeper direct SaaS experience")
    if "global" in lower_description:
        risks.append("Global scope may be a stretch")
    if salary_confidence == "low":
        risks.append("Salary range needs verification")

    official_url = apply_url or source_url or ""
    quality = source_quality(official_url, source)

    return {
        "id": re.sub(
            r"\W+",
            "-",
            f"{company}-{title}-{location}".lower(),
        ).strip("-"),
        "canonical_key": canonical_key(company, title, location),
        "company": company,
        "title": title,
        "location": location or "Location not stated",
        "location_type": loc_type,
        "track": track,
        "priority_bucket": bucket,
        "salary_min": low,
        "salary_max": high,
        "salary_period": "year",
        "salary_confidence": salary_confidence,
        "posted_at": posted_at or datetime.now(timezone.utc).date().isoformat(),
        "apply_url": official_url,
        "source_url": source_url or official_url,
        "source": source,
        "source_quality": quality,
        "fit_score": fit_score,
        "interview_probability": interview_probability,
        "application_time_minutes": application_time,
        "recommended_resume": recommended_resume,
        "cover_letter": cover_letter,
        "freshness": freshness,
        "main_risk": "; ".join(risks[:2]) or "No major gap detected",
        "job_description": description[:12_000],
        "reason": (
            f"Matches {track.lower()}, analytics, process improvement, "
            "enterprise stakeholder management, and leadership scope."
        ),
        "tags": [
            "Official/direct source" if quality >= 4 else "Broad discovery",
            track,
            bucket,
            freshness,
        ],
    }


def validate_link(job):
    url = job.get("apply_url", "")
    if not url:
        return False, "missing URL"

    try:
        body, _, final_url = request_bytes(url, timeout=20)
        text = body[:300_000].decode("utf-8", "ignore").lower()
        if any(marker in text for marker in EXPIRED_MARKERS):
            return False, "expired marker"
        if final_url:
            job["apply_url"] = final_url
        return True, ""
    except HTTPError as error:
        if error.code in (404, 410):
            return False, f"HTTP {error.code}"
        return True, f"HTTP {error.code} not treated as expired"
    except (URLError, TimeoutError):
        return True, "validation unavailable"


def scan_adzuna():
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()

    if not app_id or not app_key:
        return [], ["Adzuna credentials not configured."]

    searches = [
        "customer success director senior customer success manager client success director",
        "revenue operations director commercial operations director sales operations director",
        "business operations director business transformation director operational excellence director",
        "strategic accounts director implementation director professional services director",
    ]

    jobs = []
    warnings = []

    for group_number, query in enumerate(searches, 1):
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
        url = (
            "https://api.adzuna.com/v1/api/jobs/us/search/1?"
            + urlencode(params)
        )

        try:
            data = request_json(url)
        except Exception as error:
            warnings.append(f"Adzuna group {group_number}: {str(error)[:180]}")
            continue

        for item in data.get("results", []):
            description = clean(item.get("description", ""))
            location_data = item.get("location") or {}
            area = location_data.get("area") or []
            location = location_data.get("display_name") or (area[-1] if area else "")
            title = item.get("title", "")
            remote = "remote" in f"{title} {location} {description}".lower()

            job = normalize_job(
                company=(item.get("company") or {}).get("display_name") or "Unknown company",
                title=title,
                location=location,
                description=description,
                apply_url=item.get("redirect_url") or item.get("adref") or "",
                source="Adzuna",
                posted_at=parse_date(item.get("created")),
                salary_min=item.get("salary_min"),
                salary_max=item.get("salary_max"),
                remote=remote,
            )
            if job:
                jobs.append(job)

        time.sleep(0.2)

    return jobs, warnings


def scan_theirstack():
    api_key = os.getenv("THEIRSTACK_API_KEY", "").strip()
    if not api_key:
        return [], ["TheirStack key not configured."]

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
                headers={"Authorization": f"Bearer {api_key}"},
            )
        except Exception as error:
            warnings.append(f"TheirStack group {group_number}: {str(error)[:180]}")
            continue

        for item in data.get("data") or data.get("jobs") or []:
            url = (
                item.get("final_url")
                or item.get("url")
                or item.get("job_url")
                or ""
            )
            if not url:
                continue

            job = normalize_job(
                company=item.get("company_name") or item.get("company") or "Unknown company",
                title=item.get("job_title") or item.get("title") or "",
                location=item.get("location") or item.get("short_location") or "",
                description=clean(
                    item.get("description")
                    or item.get("description_markdown")
                    or ""
                ),
                apply_url=url,
                source="TheirStack",
                posted_at=parse_date(item.get("date_posted") or item.get("posted_at")),
                salary_min=item.get("salary_min") or item.get("min_salary"),
                salary_max=item.get("salary_max") or item.get("max_salary"),
                remote=bool(item.get("remote") or item.get("is_remote")),
            )
            if job:
                jobs.append(job)

        time.sleep(0.25)

    return jobs, warnings


def scan_greenhouse(company, slug):
    data = request_json(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    )
    return [
        normalize_job(
            company=company,
            title=item.get("title", ""),
            location=(item.get("location") or {}).get("name", ""),
            description=clean(item.get("content", "")),
            apply_url=item.get("absolute_url", ""),
            source="Greenhouse",
            posted_at=parse_date(item.get("updated_at")),
        )
        for item in data.get("jobs", [])
    ]


def scan_lever(company, slug):
    data = request_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    return [
        normalize_job(
            company=company,
            title=item.get("text", ""),
            location=(item.get("categories") or {}).get("location", ""),
            description=clean(
                f"{item.get('descriptionPlain', '')} "
                f"{item.get('additionalPlain', '')}"
            ),
            apply_url=item.get("hostedUrl", ""),
            source="Lever",
        )
        for item in data
    ]


def scan_ashby(company, slug):
    data = request_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        "?includeCompensation=true"
    )
    jobs = []

    for item in data.get("jobs", []):
        compensation = item.get("compensation") or {}
        numbers = [
            int(value)
            for value in re.findall(
                r'"(?:minValue|maxValue|value)"\s*:\s*(\d+)',
                json.dumps(compensation),
            )
        ]
        numbers = [value for value in numbers if 70_000 <= value <= 700_000]

        jobs.append(
            normalize_job(
                company=company,
                title=item.get("title", ""),
                location=item.get("location", ""),
                description=clean(item.get("descriptionPlain", "")),
                apply_url=item.get("jobUrl") or item.get("applyUrl") or "",
                source="Ashby",
                posted_at=parse_date(item.get("publishedAt")),
                salary_min=min(numbers) if numbers else None,
                salary_max=max(numbers) if numbers else None,
            )
        )
    return jobs


def scan_smartrecruiters(company, slug):
    data = request_json(
        f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100"
    )
    jobs = []

    for item in data.get("content", []):
        posting_id = item.get("id")
        details = item

        if posting_id:
            try:
                details = request_json(
                    f"https://api.smartrecruiters.com/v1/companies/"
                    f"{slug}/postings/{posting_id}"
                )
            except Exception:
                pass

        location_data = details.get("location") or item.get("location") or {}
        location = ", ".join(
            filter(
                None,
                (
                    location_data.get("city"),
                    location_data.get("region"),
                    location_data.get("country"),
                ),
            )
        )
        sections = (
            (details.get("jobAd") or {})
            .get("sections", {})
        )
        description = " ".join(
            clean((sections.get(section) or {}).get("text", ""))
            for section in (
                "jobDescription",
                "qualifications",
                "additionalInformation",
            )
        )

        jobs.append(
            normalize_job(
                company=company,
                title=details.get("name") or item.get("name") or "",
                location=location,
                description=description,
                apply_url=details.get("applyUrl") or details.get("ref") or "",
                source="SmartRecruiters",
                posted_at=parse_date(
                    details.get("releasedDate")
                    or item.get("releasedDate")
                ),
                remote="remote" in f"{location} {details.get('name', '')}".lower(),
            )
        )
    return jobs


def scan_workday(company, endpoint):
    # endpoint must be the public CXS jobs URL, for example:
    # https://company.wd5.myworkdayjobs.com/wday/cxs/company/site/jobs
    jobs = []
    offset = 0

    for _ in range(5):
        payload = {
            "appliedFacets": {},
            "limit": 20,
            "offset": offset,
            "searchText": "",
        }
        data = request_json(endpoint, method="POST", payload=payload)
        postings = (
            data.get("jobPostings")
            or data.get("items")
            or []
        )
        if not postings:
            break

        for item in postings:
            external_path = item.get("externalPath") or item.get("externalUrl") or ""
            apply_url = urljoin(endpoint.split("/wday/cxs/")[0], external_path)
            title = item.get("title") or item.get("jobTitle") or ""
            location = item.get("locationsText") or item.get("location") or ""
            description = clean(
                item.get("bulletFields")
                or item.get("subtitles")
                or ""
            )
            jobs.append(
                normalize_job(
                    company=company,
                    title=title,
                    location=location,
                    description=description,
                    apply_url=apply_url,
                    source="Workday",
                    posted_at=parse_date(item.get("postedOn")),
                    remote="remote" in f"{title} {location}".lower(),
                )
            )

        offset += len(postings)
        if len(postings) < 20:
            break

    return jobs


def scan_recruitee(company, subdomain):
    data = request_json(f"https://{subdomain}.recruitee.com/api/offers/")
    offers = data.get("offers") or data.get("data") or data
    jobs = []

    for item in offers if isinstance(offers, list) else []:
        location = (
            item.get("location")
            or item.get("location_name")
            or item.get("city")
            or ""
        )
        apply_url = (
            item.get("careers_url")
            or item.get("url")
            or item.get("apply_url")
            or ""
        )
        jobs.append(
            normalize_job(
                company=company,
                title=item.get("title") or item.get("name") or "",
                location=location,
                description=clean(
                    item.get("description")
                    or item.get("description_html")
                    or ""
                ),
                apply_url=apply_url,
                source="Recruitee",
                posted_at=parse_date(
                    item.get("published_at")
                    or item.get("created_at")
                ),
                remote=bool(item.get("remote")),
            )
        )
    return jobs


def scan_personio(company, xml_url):
    raw, _, _ = request_bytes(xml_url)
    root = ET.fromstring(raw)
    jobs = []

    for position in root.findall(".//position"):
        def text(name):
            node = position.find(name)
            return clean(node.text if node is not None else "")

        title = text("name")
        office = text("office")
        city = text("city")
        location = ", ".join(filter(None, (office, city)))
        description = " ".join(
            text(name)
            for name in (
                "jobDescriptions",
                "description",
                "requirements",
            )
        )
        apply_url = text("recruitingCategory")
        if not apply_url:
            identifier = text("id")
            apply_url = xml_url.rsplit("/xml", 1)[0]
            if identifier:
                apply_url = f"{apply_url}/job/{identifier}"

        jobs.append(
            normalize_job(
                company=company,
                title=title,
                location=location,
                description=description,
                apply_url=apply_url,
                source="Personio",
                posted_at=parse_date(text("createdAt")),
                remote="remote" in f"{location} {description}".lower(),
            )
        )
    return jobs


def json_ld_objects(page_html):
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_html,
        flags=re.I | re.S,
    )
    objects = []
    for block in blocks:
        try:
            parsed = json.loads(html.unescape(block).strip())
        except (ValueError, TypeError):
            continue

        if isinstance(parsed, list):
            objects.extend(parsed)
        elif isinstance(parsed, dict):
            graph = parsed.get("@graph")
            if isinstance(graph, list):
                objects.extend(graph)
            objects.append(parsed)
    return objects


def job_postings_from_json_ld(company, page_url, page_html, source):
    jobs = []

    for item in json_ld_objects(page_html):
        if not isinstance(item, dict):
            continue

        item_type = item.get("@type")
        if isinstance(item_type, list):
            is_job = "JobPosting" in item_type
        else:
            is_job = item_type == "JobPosting"

        if not is_job:
            continue

        organization = item.get("hiringOrganization") or {}
        company_name = (
            organization.get("name")
            if isinstance(organization, dict)
            else None
        ) or company

        location_data = item.get("jobLocation") or {}
        if isinstance(location_data, list):
            location_data = location_data[0] if location_data else {}
        address = (
            location_data.get("address", {})
            if isinstance(location_data, dict)
            else {}
        )
        if isinstance(address, str):
            location = address
        else:
            location = ", ".join(
                filter(
                    None,
                    (
                        address.get("addressLocality"),
                        address.get("addressRegion"),
                        address.get("addressCountry"),
                    ),
                )
            )

        remote = (
            str(item.get("jobLocationType", "")).upper() == "TELECOMMUTE"
            or "remote" in location.lower()
        )

        salary = item.get("baseSalary") or {}
        value = salary.get("value", {}) if isinstance(salary, dict) else {}
        if not isinstance(value, dict):
            value = {}

        apply_url = item.get("url") or page_url
        jobs.append(
            normalize_job(
                company=company_name,
                title=item.get("title", ""),
                location=location,
                description=clean(item.get("description", "")),
                apply_url=apply_url,
                source=source,
                posted_at=parse_date(item.get("datePosted")),
                salary_min=value.get("minValue"),
                salary_max=value.get("maxValue"),
                remote=remote,
            )
        )
    return jobs


def scan_jsonld(company, page_url):
    page_html, final_url = request_text(page_url)
    return job_postings_from_json_ld(
        company,
        final_url,
        page_html,
        "Employer JSON-LD",
    )


def sitemap_urls(xml_url):
    raw, _, _ = request_bytes(xml_url)
    root = ET.fromstring(raw)
    urls = []
    for node in root.findall(".//{*}loc"):
        if node.text:
            urls.append(node.text.strip())
    return urls


def scan_sitemap(company, sitemap_url):
    jobs = []
    urls = sitemap_urls(sitemap_url)

    nested_sitemaps = [
        url
        for url in urls
        if url.lower().endswith(".xml")
    ]
    page_urls = [
        url
        for url in urls
        if not url.lower().endswith(".xml")
    ]

    for nested in nested_sitemaps[:10]:
        try:
            page_urls.extend(sitemap_urls(nested))
        except Exception:
            continue

    job_like_urls = [
        url
        for url in page_urls
        if any(
            marker in url.lower()
            for marker in (
                "/job/", "/jobs/", "/career/", "/careers/",
                "/position/", "/positions/", "/vacancy/",
            )
        )
    ]

    for page_url in job_like_urls[:MAX_GENERIC_PAGES_PER_SOURCE]:
        try:
            page_html, final_url = request_text(page_url)
            jobs.extend(
                job_postings_from_json_ld(
                    company,
                    final_url,
                    page_html,
                    "Employer Sitemap",
                )
            )
        except Exception:
            continue
        time.sleep(0.05)

    return jobs


def scan_company_ats():
    if not ATS_FILE.exists():
        return [], ["company_sources.csv is missing."]

    scanners = {
        "greenhouse": scan_greenhouse,
        "lever": scan_lever,
        "ashby": scan_ashby,
        "smartrecruiters": scan_smartrecruiters,
    }

    jobs = []
    warnings = []

    with ATS_FILE.open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    for row in rows:
        if row.get("enabled", "yes").lower() != "yes":
            continue

        source_type = row.get("ats", "").strip().lower()
        scanner = scanners.get(source_type)
        if not scanner:
            continue

        try:
            jobs.extend(
                job
                for job in scanner(
                    row.get("company", "").strip(),
                    row.get("slug", "").strip(),
                )
                if job
            )
        except Exception as error:
            warnings.append(
                f"{row.get('company', source_type)}: {str(error)[:160]}"
            )
        time.sleep(0.06)

    return jobs, warnings


def scan_configured_career_sources():
    if not CAREER_SOURCE_FILE.exists():
        return [], ["career_sources.csv is missing."]

    scanners = {
        "workday": scan_workday,
        "recruitee": scan_recruitee,
        "personio": scan_personio,
        "jsonld": scan_jsonld,
        "sitemap": scan_sitemap,
        # BambooHR, Teamtailor, Jobvite, iCIMS, Oracle, and
        # SuccessFactors use jsonld/sitemap rows because their public
        # structures vary by employer.
    }

    jobs = []
    warnings = []

    with CAREER_SOURCE_FILE.open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    for row in rows:
        if row.get("enabled", "yes").lower() != "yes":
            continue

        connector = row.get("connector", "").strip().lower()
        scanner = scanners.get(connector)
        if not scanner:
            continue

        company = row.get("company", "").strip()
        endpoint = row.get("endpoint", "").strip()
        if not endpoint:
            continue

        try:
            jobs.extend(
                job
                for job in scanner(company, endpoint)
                if job
            )
        except Exception as error:
            warnings.append(
                f"{company} ({connector}): {str(error)[:160]}"
            )
        time.sleep(0.08)

    return jobs, warnings


def merge_jobs(existing, candidate):
    if candidate.get("source_quality", 0) > existing.get("source_quality", 0):
        preferred, secondary = candidate, existing
    elif candidate.get("fit_score", 0) > existing.get("fit_score", 0):
        preferred, secondary = candidate, existing
    else:
        preferred, secondary = existing, candidate

    merged = dict(secondary)
    merged.update(
        {
            key: value
            for key, value in preferred.items()
            if value not in (None, "", [])
        }
    )

    sources = set(existing.get("sources") or [existing.get("source")])
    sources.update(candidate.get("sources") or [candidate.get("source")])
    merged["sources"] = sorted(source for source in sources if source)

    return merged


def add_history_metadata(jobs, history):
    now = iso_now()

    for job in jobs:
        key = job["canonical_key"]
        previous = history.get(key)

        if previous:
            job["discovery_status"] = "Previously Seen"
            job["first_seen_at"] = previous.get("first_seen_at", now)
            job["last_seen_at"] = now
            job["days_in_feed"] = max(
                0,
                (
                    datetime.now(timezone.utc)
                    - datetime.fromisoformat(
                        job["first_seen_at"].replace("Z", "+00:00")
                    )
                ).days,
            )
        else:
            job["discovery_status"] = "New Today"
            job["first_seen_at"] = now
            job["last_seen_at"] = now
            job["days_in_feed"] = 0
            job["tags"].append("New Today")

        history[key] = {
            "company": job["company"],
            "title": job["title"],
            "location": job["location"],
            "apply_url": job["apply_url"],
            "first_seen_at": job["first_seen_at"],
            "last_seen_at": now,
            "last_source": job["source"],
            "last_fit_score": job["fit_score"],
        }

    return jobs


def diverse_rank(jobs):
    jobs.sort(
        key=lambda job: (
            1 if job.get("discovery_status") == "New Today" else 0,
            job.get("fit_score", 0),
            job.get("source_quality", 0),
            1 if job.get("freshness") == "New <72h" else 0,
            job.get("salary_max") or 0,
            job.get("posted_at") or "",
        ),
        reverse=True,
    )

    selected = []
    company_counts = Counter()

    for job in jobs:
        company_key = normalize_title(job.get("company", ""))
        if company_counts[company_key] >= MAX_PER_COMPANY:
            continue
        selected.append(job)
        company_counts[company_key] += 1
        if len(selected) >= MAX_DAILY_JOBS:
            break

    return selected


def build_coverage(provider_counts, warnings):
    automated = [
        "Adzuna",
        "TheirStack",
        "Greenhouse",
        "Lever",
        "Ashby",
        "SmartRecruiters",
        "Workday",
        "Recruitee",
        "Personio",
        "Employer JSON-LD",
        "Employer Sitemap",
    ]
    configurable = [
        "BambooHR",
        "Teamtailor",
        "Jobvite",
        "iCIMS",
        "Oracle Recruiting",
        "SAP SuccessFactors",
        "Direct company career pages",
    ]
    discovery_only = [
        "Built In",
        "Wellfound",
        "Welcome to the Jungle",
    ]

    coverage = {
        "generated_at": iso_now(),
        "automated_sources": [
            {
                "name": name,
                "active": provider_counts.get(name, 0) > 0,
                "matches": provider_counts.get(name, 0),
            }
            for name in automated
        ],
        "configurable_sources": [
            {
                "name": name,
                "active": name == "Direct company career pages"
                and (
                    provider_counts.get("Employer JSON-LD", 0)
                    + provider_counts.get("Employer Sitemap", 0)
                ) > 0,
                "note": (
                    "Add employer-specific public career URLs to "
                    "data/career_sources.csv."
                ),
            }
            for name in configurable
        ],
        "discovery_only_sources": [
            {
                "name": name,
                "active": False,
                "note": (
                    "Not scraped. May appear indirectly through a broad provider."
                ),
            }
            for name in discovery_only
        ],
        "warnings": warnings[:120],
    }

    COVERAGE_FILE.write_text(
        json.dumps(coverage, indent=2),
        encoding="utf-8",
    )
    return coverage


def main():
    history = load_history()

    source_results = []
    warnings = []

    scanners = [
        ("Adzuna", scan_adzuna),
        ("TheirStack", scan_theirstack),
        ("Direct ATS", scan_company_ats),
        ("Configured career sites", scan_configured_career_sources),
    ]

    for label, scanner in scanners:
        try:
            jobs, scanner_warnings = scanner()
            source_results.extend(jobs)
            warnings.extend(scanner_warnings)
            print(f"{label}: {len(jobs)} qualifying matches.")
        except Exception as error:
            warnings.append(f"{label}: fatal connector error: {str(error)[:180]}")

    unique = {}
    for job in source_results:
        if not job or not job.get("apply_url"):
            continue

        key = job["canonical_key"]
        if key in unique:
            unique[key] = merge_jobs(unique[key], job)
        else:
            job["sources"] = [job.get("source")]
            unique[key] = job

    candidates = add_history_metadata(
        list(unique.values()),
        history,
    )

    validated = []
    for job in candidates:
        valid, note = validate_link(job)
        job["link_validation"] = note
        if valid:
            validated.append(job)

    selected = diverse_rank(validated)

    for index, job in enumerate(selected):
        job["top_10_today"] = index < 10
        if index < 10 and "Top 10 Today" not in job["tags"]:
            job["tags"].append("Top 10 Today")

    provider_counts = Counter(
        source
        for job in source_results
        if job
        for source in (job.get("sources") or [job.get("source")])
        if source
    )
    coverage = build_coverage(provider_counts, warnings)

    new_today_count = sum(
        1
        for job in selected
        if job.get("discovery_status") == "New Today"
    )

    payload = {
        "updated_at": iso_now(),
        "minimum_salary": MIN_SALARY,
        "daily_job_cap": MAX_DAILY_JOBS,
        "maximum_jobs_per_company": MAX_PER_COMPANY,
        "broad_search_enabled": bool(
            provider_counts.get("Adzuna")
            or provider_counts.get("TheirStack")
        ),
        "provider_status": {
            item["name"]: {
                "active": item["active"],
                "matches": item["matches"],
            }
            for item in coverage["automated_sources"]
        },
        "jobs": selected,
        "match_count": len(selected),
        "new_today_count": new_today_count,
        "qualified_before_validation": len(candidates),
        "qualified_after_validation": len(validated),
        "discovered_before_cap": len(validated),
        "errors": warnings[:120],
    }

    OUT.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    save_history(history)

    print(
        f"Published {len(selected)} jobs; {new_today_count} are new today. "
        f"Maximum {MAX_PER_COMPANY} jobs per company. "
        f"Salary floor: ${MIN_SALARY:,}."
    )


if __name__ == "__main__":
    main()
