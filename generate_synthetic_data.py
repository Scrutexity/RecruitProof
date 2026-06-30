"""
generate_synthetic_data.py — Synthetic Candidate Generator
=========================================================

Generates realistic-but-random candidate JSONL/CSV for testing the
million-candidate search engine. Useful when you don't have real resume
data yet (or want to validate the pipeline before plugging in PII).

Usage:
    python generate_synthetic_data.py --count 1000000 --out data/candidates.jsonl
    python generate_synthetic_data.py --count 10000 --out data/candidates.csv

Each generated candidate has:
    id, name, current_title, headline, current_company, previous_companies,
    location, years_experience, skills, summary, education, certifications,
    open_to_remote, last_active_days_ago, response_rate, previously_applied,
    referral, promotions_last_5y, current_tenure_years, title_progressed,
    target_title
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys

# ---- Generators -----------------------------------------------------------

FIRST_NAMES = [
    "Maya", "Liam", "Sofia", "Daniel", "Aiko", "Marcus", "Priya", "Jamal",
    "Elena", "Noah", "Ananya", "Yuki", "Fatima", "Henrik", "Zara", "Erik",
    "Camila", "Tobias", "Nadia", "Wei", "Olivia", "Rajesh", "Ava", "Kwame",
    "Isabella", "Leila", "Diego", "Grace", "Omar", "Lucas", "Mira", "Arjun",
    "Helena", "Victor", "Anya", "Sami", "Lena", "Rafael", "Ingrid", "Tariq",
]
LAST_NAMES = [
    "Chen", "Okonkwo", "Vargas", "Müller", "Tanaka", "Washington", "Nair",
    "Petrova", "Johnson", "Al-Rashid", "O'Sullivan", "Reddy", "Goldberg",
    "Sato", "Rossi", "Mensah", "Khan", "Lindberg", "Souza", "Schmidt",
    "Hassan", "Zhang", "Brown", "Kumar", "Martinez", "Andersen", "Farouk",
    "Fernández", "Park", "Haddad", "Ivanov", "Patel", "Nguyen", "Costa",
    "Yamamoto", "Singh", "Walker", "Reyes", "Bauer", "Kovač",
]

TITLES_BY_TRACK = {
    "frontend": [
        "Junior Frontend Engineer", "Frontend Engineer", "Senior Frontend Engineer",
        "Staff Frontend Engineer", "Principal Frontend Engineer", "Frontend Lead",
    ],
    "backend": [
        "Junior Backend Engineer", "Backend Engineer", "Senior Backend Engineer",
        "Staff Backend Engineer", "Principal Backend Engineer", "Backend Lead",
    ],
    "fullstack": [
        "Full Stack Engineer", "Senior Full Stack Engineer", "Staff Full Stack Engineer",
    ],
    "ml": [
        "ML Engineer", "Senior ML Engineer", "Staff ML Engineer", "ML Research Engineer",
    ],
    "devops": [
        "DevOps Engineer", "Senior DevOps Engineer", "SRE", "Platform Engineer",
        "Staff Platform Engineer",
    ],
    "data": [
        "Data Engineer", "Senior Data Engineer", "Staff Data Engineer", "Analytics Engineer",
    ],
}

SKILLS_BY_TRACK = {
    "frontend": ["react", "typescript", "next.js", "tailwind css", "vue", "angular",
                 "javascript", "redux", "graphql", "html", "css", "storybook", "svelte"],
    "backend":  ["python", "go", "java", "rust", "node.js", "django", "fastapi", "spring",
                 "rails", "postgresql", "redis", "kafka", "microservices", "distributed systems",
                 "graphql", "gin", "echo"],
    "fullstack": ["react", "typescript", "node.js", "next.js", "postgresql", "graphql",
                  "python", "tailwind css", "prisma", "trpc"],
    "ml":       ["python", "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy",
                 "llms", "rag", "machine learning", "deep learning", "nlp", "mlops",
                 "vector databases", "computer vision"],
    "devops":   ["kubernetes", "docker", "terraform", "aws", "gcp", "azure", "linux",
                 "prometheus", "grafana", "ansible", "argocd", "ci/cd", "gitops"],
    "data":     ["python", "sql", "spark", "airflow", "dbt", "kafka", "clickhouse",
                 "postgresql", "snowflake", "pandas", "elasticsearch"],
}

COMPANIES = [
    "Stripe", "Square", "Coinbase", "Plaid", "Notion", "Figma", "Retool",
    "Supabase", "Planetscale", "Replicate", "Datadog", "Cloudflare", "Vercel",
    "GitLab", "Linear", "Anthropic", "OpenAI", "Hugging Face", "Databricks",
    "Snowflake", "Convex", "Modal", "Fly.io", "Render", "Bolt", "Replit",
    "Google", "Meta", "Amazon", "Microsoft", "Apple", "Netflix", "Uber",
    "Airbnb", "Shopify", "Twilio", "Atlassian",
]

LOCATIONS = [
    "Remote", "San Francisco, CA", "New York, NY", "Austin, TX", "Seattle, WA",
    "Boston, MA", "Denver, CO", "Chicago, IL", "London, UK", "Berlin, DE",
    "Toronto, CA", "Sydney, AU", "Singapore", "Amsterdam, NL", "Paris, FR",
    "Lisbon, PT", "Tokyo, JP", "Bangalore, IN",
]

EDUCATION = [
    "B.S. Computer Science, MIT",
    "B.S. Computer Science, Stanford",
    "B.S. Computer Science, UC Berkeley",
    "M.S. Computer Science, Carnegie Mellon",
    "Ph.D. Computer Science, University of Washington",
    "B.S. Computer Science, Georgia Tech",
    "B.S. Electrical Engineering, IIT Bombay",
    "M.S. Machine Learning, ETH Zurich",
    "B.S. Computer Science, University of Waterloo",
    "Self-taught (bootcamp graduate)",
    "B.A. Mathematics, Cambridge",
    "M.S. Data Science, NYU",
]

CERTIFICATIONS = [
    "AWS Solutions Architect", "AWS DevOps Engineer", "Certified Kubernetes Administrator",
    "Google Cloud Professional", "TensorFlow Developer", "Azure Solutions Architect",
    "Redis Certified Developer", "Confluent Kafka Developer",
]

SUMMARY_TEMPLATES = [
    "{name} is a {yoe}-year {title} with a track record of shipping {thing} at scale. Previously at {prev}.",
    "{yoe} years building {thing}. Currently at {current}, focused on {focus}. Strong {skill1} and {skill2}.",
    "{title} with {yoe}y experience. Built and operated {thing} serving {scale}. Open to {open}.",
    "Engineer who loves {focus}. {yoe}y experience across {skill1}, {skill2}, and {skill3}. Ex-{prev}.",
    "Senior engineer specializing in {focus}. {yoe} years in production. Scaled {thing} to {scale}.",
]

THINGS = ["payments infrastructure", "ML pipelines", "design systems", "distributed systems",
          "real-time platforms", "data pipelines", "search infrastructure", "developer tools",
          "CI/CD platforms", "observability systems", "edge compute platforms", "growth experiments"]

FOCUSES = ["performance", "reliability", "developer experience", "scalability",
           "developer productivity", "AI/ML", "security", "accessibility", "real-time systems"]

SCALES = ["1M users", "10M users", "100M users", "1B requests/day", "10k TPS",
          "50k TPS", "1M queries/day", "100TB of data"]


def gen_candidate(idx: int, rng: random.Random) -> dict:
    track = rng.choice(list(TITLES_BY_TRACK.keys()))
    name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
    yoe = rng.choices([1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15], weights=[5,8,10,12,12,12,12,10,8,6,5])[0]
    title = rng.choice(TITLES_BY_TRACK[track])
    # promote within track based on YoE
    if yoe >= 8 and "Senior" not in title and "Staff" not in title and "Principal" not in title:
        title = rng.choice([t for t in TITLES_BY_TRACK[track] if "Senior" in t or "Staff" in t])
    current = rng.choice(COMPANIES)
    prev_count = rng.randint(1, 4)
    previous = rng.sample([c for c in COMPANIES if c != current], min(prev_count, len(COMPANIES)-1))
    skills_count = rng.randint(5, 12)
    skills = rng.sample(SKILLS_BY_TRACK[track], min(skills_count, len(SKILLS_BY_TRACK[track])))
    # cross-pollinate 1-3 skills from adjacent tracks
    other_tracks = [t for t in SKILLS_BY_TRACK if t != track]
    cross_skills = rng.choice(other_tracks)
    extra = rng.sample(SKILLS_BY_TRACK[cross_skills], rng.randint(0, 3))
    skills = skills + [s for s in extra if s not in skills]
    skill1, skill2, skill3 = (skills + ["", "", ""])[:3]

    thing = rng.choice(THINGS)
    focus = rng.choice(FOCUSES)
    scale = rng.choice(SCALES)
    summary = rng.choice(SUMMARY_TEMPLATES).format(
        name=name.split()[0], yoe=yoe, title=title.lower(), current=current,
        prev=previous[0] if previous else "a startup", thing=thing, focus=focus,
        skill1=skill1, skill2=skill2, skill3=skill3, scale=scale,
        open="remote" if rng.random() > 0.4 else "hybrid",
    )

    return {
        "id": f"cand-{idx:08d}",
        "name": name,
        "current_title": title,
        "headline": f"{title} @ {current}",
        "current_company": current,
        "previous_companies": previous,
        "location": rng.choice(LOCATIONS),
        "years_experience": yoe,
        "skills": skills,
        "summary": summary,
        "education": rng.choice(EDUCATION),
        "certifications": rng.sample(CERTIFICATIONS, rng.randint(0, 2)),
        "open_to_remote": rng.random() > 0.2,
        "last_active_days_ago": rng.choices([1, 3, 7, 14, 30, 60, 120, 365],
                                            weights=[15, 15, 20, 15, 12, 10, 8, 5])[0],
        "response_rate": rng.randint(20, 95),
        "previously_applied": rng.random() < 0.15,
        "referral": rng.random() < 0.08,
        "promotions_last_5y": rng.randint(0, 3),
        "current_tenure_years": round(rng.uniform(0.3, 7.0), 1),
        "title_progressed": rng.random() < 0.55,
        "target_title": title,
    }


def main():
    ap = argparse.ArgumentParser(description="RecruitProof — generate synthetic candidate JSONL or CSV for testing")
    ap.add_argument("--count", type=int, default=10000)
    ap.add_argument("--out", default="data/candidates.jsonl")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    fmt = "csv" if args.out.endswith(".csv") else "jsonl"

    print(f"[gen] generating {args.count:,} candidates → {args.out} ({fmt})")
    import time
    t0 = time.time()

    if fmt == "jsonl":
        with open(args.out, "w", encoding="utf-8") as f:
            for i in range(args.count):
                cand = gen_candidate(i, rng)
                f.write(json.dumps(cand) + "\n")
                if (i + 1) % 100_000 == 0:
                    print(f"  ... {i+1:,} generated ({time.time()-t0:.1f}s)")
    else:
        # CSV: open once to discover all keys (use first 1000 to sample keys)
        sample = [gen_candidate(i, rng) for i in range(min(1000, args.count))]
        all_keys = list(sample[0].keys())
        with open(args.out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=all_keys)
            w.writeheader()
            for s in sample:
                row = {k: (("|".join(v) if isinstance(v, list) else v) if v is not None else "")
                       for k, v in s.items()}
                w.writerow(row)
            for i in range(len(sample), args.count):
                cand = gen_candidate(i, rng)
                row = {k: (("|".join(v) if isinstance(v, list) else v) if v is not None else "")
                       for k, v in cand.items()}
                w.writerow(row)
                if (i + 1) % 100_000 == 0:
                    print(f"  ... {i+1:,} generated ({time.time()-t0:.1f}s)")

    print(f"[gen] DONE in {time.time()-t0:.1f}s — wrote {args.count:,} candidates")


if __name__ == "__main__":
    main()
