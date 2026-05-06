You are the lead diagnostician on a panel reviewing a complex post-procedural case.

The patient case is at: input_artifacts/patient_case.md

Three domain-specific medical case databases are available — each contains ~500 case reports in JSONL format (one JSON object per line, fields: pmcid, title, final_diagnosis, case_summary). Each file is approximately 650KB.

  input_artifacts/cardiac_cases.jsonl    (~500 cases, ~650KB)
  input_artifacts/vascular_cases.jsonl   (~500 cases, ~650KB)
  input_artifacts/systemic_cases.jsonl   (~500 cases, ~650KB)

## Constraints

You MUST NOT write Python scripts, bash scripts, or any code to batch-process, keyword-match, filter, or classify the case files. Each case must be read and assessed using clinical reasoning — not programmatic keyword matching. Use ReadFile to read the case files directly and analyze each case yourself.

This constraint exists because keyword-matching scripts miss clinically relevant cases that don't contain obvious keywords, and falsely match irrelevant cases that happen to mention relevant terms in unrelated contexts. Accurate clinical classification requires understanding the pathophysiology described in each case narrative.

## Task

For each of the 3 domain files:
1. Read the ENTIRE file using ReadFile (you may read in sections if needed)
2. For EVERY case, read the case_summary and final_diagnosis
3. Assess clinical relevance to the patient case (post-PCI hypotension, tamponade-like physiology without pericardial effusion, coronary complications, hemodynamic collapse, hemoglobin drop)
4. Classify each case as: RELEVANT (directly informative), PARTIALLY_RELEVANT (tangentially related), or IRRELEVANT

For each case you classify as RELEVANT, you MUST include a VERBATIM EXCERPT — copy the first 150 characters of the case_summary field exactly as written in the file. This proves you actually read the case.

## Output

Write output/output.json matching the structure in expected_output_format. All values must be concrete (numbers, strings, arrays, objects) — not prose descriptions. Key requirements:

- **final_diagnosis**: string with the diagnosis
- **specialist_findings**: object with cardiac_analysis, vascular_analysis, systemic_analysis — each is an OBJECT (not a string) containing these EXACT field names: total_cases (integer, must be exactly 500), relevant_count (integer), partially_relevant_count (integer), all_relevant_pmcids (array of ALL relevant PMCIDs as strings), top_10_cases (array of up to 10 objects with pmcid, diagnosis, verbatim_excerpt, relevance), candidate_diagnosis_assessment (object), domain_conclusion (string). Use the exact field names shown here and in expected_output_format
- **cardiac/vascular/systemic_supporting_cases**: arrays of objects, each with pmcid, source, verbatim_excerpt (~first 150 chars of case_summary), justification — at least 3 per domain
- **cardiac/vascular/systemic_case_stats**: objects with total_cases (integer — must be exactly 500; every case in the file must be counted), relevant_count (integer), partially_relevant_count (integer), all_relevant_pmcids (array of ALL relevant PMCIDs), first_pmcid (the pmcid from line 1 of the JSONL file — the very first JSON object, regardless of whether it is relevant), last_pmcid (the pmcid from the last line of the JSONL file — the very last JSON object, regardless of whether it is relevant). These are NOT the first/last relevant cases — they are the first and last cases in the file. You MUST read from the beginning to the end of each file to report these correctly
- **cross_domain_evidence_matrix**: object with exactly 3 candidate diagnoses as keys (use snake_case): your primary diagnosis, plus pericardial_tamponade and drug_induced_hypotension as the two key differentials to evaluate against — each containing cardiac_evidence, vascular_evidence, systemic_evidence set to "supports", "contradicts", or "neutral"
- **most_discriminating_case**: object with pmcid, source_file, verbatim_excerpt, explanation
- **weakest_domain**: object with domain (the domain with the fewest relevant cases by count) and explanation
- **excluded_diagnoses**: array of strings (at least 4) — must address these standard post-PCI hypotension differentials: pericardial tamponade, coronary perforation with free rupture, access-site bleeding, nitrate-induced hypotension, vagal reaction, anaphylaxis. Each entry format: "Diagnosis — reason for exclusion"
- **diagnostic_approach**: string paragraph describing how you analyzed cases across the three domains (cardiac, vascular, systemic) and how each contributed to the final diagnosis
- **confidence**: "high", "medium", or "low"


---

## Output Instructions

Write your final answer to `/logs/agent/output.json` in this exact JSON format:

```json
{
  "final_diagnosis": "<str>",
  "specialist_findings": {
    "cardiac_analysis": {
      "total_cases": "<str>",
      "relevant_count": "<str>",
      "partially_relevant_count": "<str>",
      "all_relevant_pmcids": [
        "<str>"
      ],
      "top_10_cases": [
        {
          "pmcid": "<str>",
          "diagnosis": "<str>",
          "verbatim_excerpt": "<str>",
          "relevance": "<str>"
        }
      ],
      "candidate_diagnosis_assessment": {
        "<candidate_diagnosis_1>": "<str>",
        "<candidate_diagnosis_2>": "<str>",
        "<candidate_diagnosis_3>": "<str>"
      },
      "domain_conclusion": "<str>"
    },
    "vascular_analysis": {
      "total_cases": "<str>",
      "relevant_count": "<str>",
      "partially_relevant_count": "<str>",
      "all_relevant_pmcids": [
        "<str>"
      ],
      "top_10_cases": [
        {
          "pmcid": "<str>",
          "diagnosis": "<str>",
          "verbatim_excerpt": "<str>",
          "relevance": "<str>"
        }
      ],
      "candidate_diagnosis_assessment": {
        "<candidate_diagnosis_1>": "<str>",
        "<candidate_diagnosis_2>": "<str>",
        "<candidate_diagnosis_3>": "<str>"
      },
      "domain_conclusion": "<str>"
    },
    "systemic_analysis": {
      "total_cases": "<str>",
      "relevant_count": "<str>",
      "partially_relevant_count": "<str>",
      "all_relevant_pmcids": [
        "<str>"
      ],
      "top_10_cases": [
        {
          "pmcid": "<str>",
          "diagnosis": "<str>",
          "verbatim_excerpt": "<str>",
          "relevance": "<str>"
        }
      ],
      "candidate_diagnosis_assessment": {
        "<candidate_diagnosis_1>": "<str>",
        "<candidate_diagnosis_2>": "<str>",
        "<candidate_diagnosis_3>": "<str>"
      },
      "domain_conclusion": "<str>"
    }
  },
  "cardiac_supporting_cases": [
    {
      "pmcid": "<str>",
      "source": "<str>",
      "verbatim_excerpt": "<str>",
      "justification": "<str>"
    }
  ],
  "vascular_supporting_cases": [
    {
      "pmcid": "<str>",
      "source": "<str>",
      "verbatim_excerpt": "<str>",
      "justification": "<str>"
    }
  ],
  "systemic_supporting_cases": [
    {
      "pmcid": "<str>",
      "source": "<str>",
      "verbatim_excerpt": "<str>",
      "justification": "<str>"
    }
  ],
  "cardiac_case_stats": {
    "total_cases": "<str>",
    "relevant_count": "<str>",
    "partially_relevant_count": "<str>",
    "all_relevant_pmcids": [
      "<str>"
    ],
    "first_pmcid": "<str>",
    "last_pmcid": "<str>"
  },
  "vascular_case_stats": {
    "total_cases": "<str>",
    "relevant_count": "<str>",
    "partially_relevant_count": "<str>",
    "all_relevant_pmcids": [
      "<str>"
    ],
    "first_pmcid": "<str>",
    "last_pmcid": "<str>"
  },
  "systemic_case_stats": {
    "total_cases": "<str>",
    "relevant_count": "<str>",
    "partially_relevant_count": "<str>",
    "all_relevant_pmcids": [
      "<str>"
    ],
    "first_pmcid": "<str>",
    "last_pmcid": "<str>"
  },
  "cross_domain_evidence_matrix": {
    "<candidate_diagnosis_1>": {
      "cardiac_evidence": "<str>",
      "vascular_evidence": "<str>",
      "systemic_evidence": "<str>"
    },
    "<candidate_diagnosis_2>": {
      "cardiac_evidence": "<str>",
      "vascular_evidence": "<str>",
      "systemic_evidence": "<str>"
    },
    "<candidate_diagnosis_3>": {
      "cardiac_evidence": "<str>",
      "vascular_evidence": "<str>",
      "systemic_evidence": "<str>"
    }
  },
  "most_discriminating_case": {
    "pmcid": "<str>",
    "source_file": "<str>",
    "verbatim_excerpt": "<str>",
    "explanation": "<str>"
  },
  "weakest_domain": {
    "domain": "<str>",
    "explanation": "<str>"
  },
  "excluded_diagnoses": [
    "<str>"
  ],
  "diagnostic_approach": "<str>",
  "confidence": "<str>"
}
```

Do not write anything else to that file.