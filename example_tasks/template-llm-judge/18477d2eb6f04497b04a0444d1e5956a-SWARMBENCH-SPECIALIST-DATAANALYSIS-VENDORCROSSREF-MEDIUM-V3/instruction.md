You have access to 10 independent technology vendor assessment reports in the input_artifacts/ directory. Each report was prepared by a different analyst firm evaluating a different technology vendor. The reports cover financial performance, technical architecture, security posture, and market positioning.

Your task is to perform a comprehensive cross-document analysis to identify ALL factual contradictions BETWEEN reports. A contradiction exists when two or more reports make claims that cannot both be true simultaneously.

You must analyze the reports across 4 specialist domains with STRICT boundaries:

1. FINANCIAL — Covers ONLY: revenue/ARR figures, year-over-year growth rates, total addressable market (TAM) size estimates, market share percentages, and company valuations. If a claim involves a dollar amount, a percentage growth rate, or a market size number, it belongs here.

2. TECHNICAL — Covers ONLY: performance throughput benchmarks (events/sec, latency, uptime percentages), encryption ALGORITHMS and STANDARDS (e.g., AES-128 vs AES-256 — the algorithm itself), API/protocol feature compatibility percentages, and first-to-market technology claims. If a claim involves a measurable technical specification or a technology priority dispute, it belongs here.

3. SECURITY — Covers ONLY: compliance certification names and TIMELINES (e.g., when SOC 2 was achieved), exclusive compliance certification claims (e.g., 'only vendor with FedRAMP High'), data breach or incident history, compliance SCOPE across product modules (e.g., whether all modules are HIPAA certified), and encryption KEY MANAGEMENT practices (e.g., customer-managed keys vs provider-managed keys — how keys are managed, not which algorithm is used). If a claim involves a certification date, a security incident, or compliance coverage, it belongs here.

4. MARKET — Covers ONLY: partnership exclusivity claims (e.g., 'exclusive partnership with X'), customer count disputes, market leadership/ranking claims (e.g., '#1 in distributed computing'), customer deployment size references (e.g., 'N nodes at Customer Y'), and industry award claims (e.g., 'Gartner Leader'). If a claim involves a customer relationship, a market position, or an award, it belongs here.

IMPORTANT DOMAIN RULES:
- Encryption ALGORITHM disputes (AES-128 vs AES-256) → TECHNICAL
- Encryption KEY MANAGEMENT disputes (CMEK vs provider-managed) → SECURITY
- Revenue or market share numbers → FINANCIAL (even if about a security company)
- Partnership or customer claims → MARKET (even if about a technical product)

CRITICAL COUNTING RULES:
- Only count CROSS-DOCUMENT contradictions (claims from DIFFERENT reports that conflict). Do NOT count internal inconsistencies within a single report.
- If 3+ companies all make mutually exclusive claims about the SAME metric or title (e.g., multiple companies each claiming '#1 market leader', or multiple market share claims summing over 100%), report it as ONE contradiction entry with ALL involved companies listed in companies_involved. Do NOT split into separate pairwise entries.
- Use report_a/report_b for the primary two reports, and include additional_reports if more than 2 reports are involved.
- Ignore approximate vs exact figures that are consistent (e.g., '$95M' vs '$90-100M range' is NOT a contradiction).
- most_contested_domain is the domain with the HIGHEST number of contradiction entries.

For each contradiction found, provide:
- id: A unique ID (format: DOMAIN-NNN, e.g. FIN-001, TECH-002)
- domain: One of 'financial', 'technical', 'security', 'market'
- type: Brief type label (e.g., 'market_size_disagreement')
- companies_involved: List of ALL company names involved
- description: Description of the contradiction
- report_a: Filename of first report
- quote_from_report_a: Exact verbatim quote from report A
- report_b: Filename of second report
- quote_from_report_b: Exact verbatim quote from report B

Also provide a summary with:
- total_contradictions_found (integer — must equal length of contradictions array)
- financial_count, technical_count, security_count, market_count (integers — must sum to total)
- company_with_most_contradictions (company name appearing in the most contradiction entries)
- most_contested_domain (the domain with the highest count among the four)

Write your final answer as JSON to output/output.json.


---

## Output Instructions

Write your final answer to `/logs/agent/output.json` in this exact JSON format:

```json
{
  "contradictions": [
    {
      "id": "<str>",
      "domain": "<str>",
      "type": "<str>",
      "companies_involved": [
        "<str>"
      ],
      "description": "<str>",
      "report_a": "<str>",
      "quote_from_report_a": "<str>",
      "report_b": "<str>",
      "quote_from_report_b": "<str>",
      "additional_reports": {
        "report_Z.txt": "<str>"
      }
    }
  ],
  "summary": {
    "total_contradictions_found": "<int>",
    "financial_count": "<int>",
    "technical_count": "<int>",
    "security_count": "<int>",
    "market_count": "<int>",
    "company_with_most_contradictions": "<str>",
    "most_contested_domain": "<str>"
  }
}
```

Do not write anything else to that file.