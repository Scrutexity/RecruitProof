export const metrics = [
  { label: "CVs Received", value: "1,024,871", sub: "▲ 12,400 this week", tone: "good" },
  { label: "PDFs Parsed", value: "892,341", sub: "87% of archive", tone: "good" },
  { label: "Word Parsed", value: "132,530", sub: "13% of archive", tone: "good" },
  { label: "Failed Files", value: "127", sub: "0.01% needs repair", tone: "warn" },
  { label: "Duplicates", value: "18,432", sub: "1.8% wasted storage", tone: "warn" },
  { label: "Search Latency", value: "4.2ms", sub: "warm FAISS lookup", tone: "good" },
];

export const candidates = [
  {
    rank: 1,
    name: "Kwame O'Sullivan",
    title: "Senior Backend Engineer",
    score: "8.16",
    missing: "AWS, Kubernetes",
    proof: "4 years at Vercel · 3 promotions · 92% semantic match",
    matched: ["Go", "Postgres", "Distributed systems", "Payments", "API design"],
    why: "Career velocity and backend depth make him a high-confidence rediscovery candidate even though exact cloud keywords are incomplete.",
  },
  {
    rank: 2,
    name: "Elena Vasquez",
    title: "Staff Engineer, Payments",
    score: "7.92",
    missing: "Kafka",
    proof: "7 years at Stripe · Led 12-person team · Payments infra",
    matched: ["Leadership", "Python", "Ledger systems", "Risk", "Platform engineering"],
    why: "Strong seniority and payments relevance with one keyword gap that likely reflects resume wording rather than capability.",
  },
  {
    rank: 3,
    name: "James Park",
    title: "Lead Backend (Go)",
    score: "7.75",
    missing: "GraphQL",
    proof: "6 years at Uber · Distributed systems expert",
    matched: ["Go", "Microservices", "Queues", "Observability", "High-scale systems"],
    why: "Excellent infrastructure match for backend leadership roles; missing GraphQL keeps him below the top two.",
  },
];

export const nav = [
  ["executive", "Executive Dashboard"],
  ["import", "Import Center"],
  ["intelligence", "Intelligence Dashboard"],
  ["search", "Enterprise Search"],
  ["candidate", "Candidate Intelligence"],
  ["roi", "Executive ROI"],
  ["migration", "Migration Center"],
  ["audit", "Audit Center"],
  ["trust", "Trust Center"],
  ["report", "Million-CV Report"],
  ["storyboard", "Demo Storyboard"],
  ["docs", "Docs"],
] as const;

export const docs = [
  "proof/million_cv_scan/README.md",
  "proof/million_cv_scan/sample_report.md",
  "proof/million_cv_scan/benchmark_plan.md",
  "proof/million_cv_scan/ingestion_checklist.md",
  "proof/million_cv_scan/encore_export_format.md",
  "DEPLOYMENT.md",
  "SECURITY.md",
  "SECURITY_BRIEF.md",
  "AUDIT_AND_COMPLIANCE.md",
  "PERFORMANCE.md",
  "INTEGRATIONS.md",
  "ENCORE_MIGRATION.md",
  "SAMPLE_OUTPUT.md",
  "ARCHITECTURE.md",
  "ROADMAP.md",
];
