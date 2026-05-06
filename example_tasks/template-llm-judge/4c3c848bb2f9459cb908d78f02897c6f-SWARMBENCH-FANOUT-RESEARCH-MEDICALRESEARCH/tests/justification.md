# Oracle Justification — SWARMBENCH-FANOUT-RESEARCH-MEDICAL

## Patient Summary

A 75-year-old woman with treated hypertension and stable angina underwent PCI of a chronic total occlusion (CTO) in the proximal RCA via dual access (right radial 6Fr, right femoral 8Fr). After crossing the occlusion and stent deployment, her blood pressure fell to 60/40 mmHg, refractory to fluid boluses and IV phenylephrine. She had elevated venous pressures. Echocardiogram showed **no pericardial effusion**. Angiograms showed no coronary perforation. Femoral angiography excluded access-site bleeding. An IABP was inserted (systolic 100 mmHg). Hemoglobin dropped from 13.2 to 11 g/dL. CT scan was ordered to rule out retroperitoneal bleed.

Source: PMC7042146 via zou-lab/MedCaseReasoning (HuggingFace).

---

## Diagnosis: Intramural Haematoma

The diagnosis is **coronary intramural haematoma** (also: intramyocardial dissecting haematoma, contained haematoma with pseudotamponade). The mechanism is a contained micro-perforation from the extensive coronary dissection during CTO-PCI, causing blood to dissect into the vessel wall and AV groove region. This produces tamponade-like physiology (elevated venous pressures, refractory hypotension) WITHOUT pericardial effusion, because the bleeding is contained within the intramural/intramyocardial space rather than rupturing into the pericardial sac.

### Key clinical features supporting this diagnosis

| Finding | Significance |
|---|---|
| Post-PCI hypotension (60/40 mmHg) | Hemodynamic collapse from mechanical compression |
| Refractory to fluids + vasopressors | Not pharmacologic (rules out nitrates, vagal) |
| Elevated venous pressures | Tamponade physiology / obstructive shock |
| No pericardial effusion on echo | Rules out classic tamponade; points to contained/intramural bleeding |
| No coronary perforation on angiogram | Rules out free rupture; consistent with contained micro-perforation |
| Hemoglobin drop (13.2 → 11 g/dL) | Active bleeding into a closed space |
| IABP restored systolic to 100 mmHg | Mechanical support effective (consistent with obstructive physiology) |
| Extensive dissection during CTO crossing | Creates the substrate for intramural haematoma formation |

### Why this is NOT another diagnosis

| Excluded Diagnosis | Reason |
|---|---|
| Pericardial tamponade | Echo showed no pericardial effusion |
| Coronary perforation with free rupture | Angiogram showed no extravasation; free rupture would cause pericardial effusion |
| Access-site / retroperitoneal bleeding | Femoral angiography excluded access-site bleeding |
| Nitrate-induced hypotension | Refractory to fluids and vasopressors; hemoglobin drop indicates bleeding |
| Vagal reaction | No bradycardia; refractory course requiring IABP |
| Anaphylaxis | No urticaria or bronchospasm; no response to antihistamines |

---

## Why Fan-Out-Synthesize Is the Right Pattern

This task requires reading ~1500 medical case reports across three domain-specific databases (~500 cases × 3 domains, ~650KB each, ~500K tokens total). A single agent cannot effectively read and clinically assess all 1500 cases within its context window. The fan-out pattern solves this:

1. **Phase 1 (15 chunk-readers):** 5 sub-agents per domain, each reading ~100 cases. This keeps each sub-agent's context manageable (~33K tokens of case narratives).
2. **Phase 2 (3 domain synthesizers):** One per domain, merging the 5 chunk reports into a domain-level analysis with total_cases, relevant PMCIDs, and diagnostic assessment.
3. **Phase 3 (1 final synthesizer):** Cross-domain synthesis producing the final diagnosis and output.

The task tests whether the orchestrator can:
- Decompose the workload effectively across sub-agents
- Ensure complete coverage (all 500 cases per file, not just partial reads)
- Maintain clinical reasoning quality (not degrade to keyword matching)
- Synthesize independent domain analyses into a coherent diagnosis

---

## Gold Standard PMCIDs

The following PMCIDs are objectively relevant — their titles and diagnoses directly match the patient's condition. Any competent clinical review of the case databases should identify these.

### Cardiac domain (cardiac_cases.jsonl)

| PMCID | Title | Final Diagnosis |
|---|---|---|
| PMC9364049 | Coronary artery intramural hematoma, a rare complication of percutaneous coronary intervention | Coronary intramural hematoma |
| PMC9332897 | Conservatively treated intramyocardial dissecting haematoma of the interventricular septum | Intramyocardial dissecting haematoma |
| PMC7954273 | Recovery after large intramyocardial dissecting haematoma of the ventricular septum | Intramyocardial haematoma |

These three are **required** in the gold standard — they are exact pathophysiological matches. An agent that reads cardiac_cases.jsonl and fails to identify at least 2 of these 3 has not performed adequate clinical assessment.

### Vascular domain (vascular_cases.jsonl)

| PMCID | Title | Relevance |
|---|---|---|
| PMC8872004 | Iliacus Muscle Hematoma | Contained hematoma with hemoglobin drop in post-procedure setting |
| PMC8684169 | Spontaneous rupture of the ovarian vein (nutcracker syndrome) | Retroperitoneal hematoma diagnosed by CT |
| PMC3505917 | Pseudoaneurysm Accompanied by Crowe Type IV DDH | Contained hemorrhage with hemodynamic collapse |
| PMC6195931 | Vascular pseudoaneurysm | Acute vascular catastrophe with refractory hypotension |
| PMC3971853 | Profunda femoris pseudoaneurysm | Delayed post-procedure contained hematoma |

### Systemic domain (systemic_cases.jsonl)

| PMCID | Title | Relevance |
|---|---|---|
| PMC4229935 | Idiopathic systemic capillary leak syndrome | Refractory hypotension pattern |
| PMC4194386 | Hodgkin lymphoma with refractory hypotension | Vasopressor-refractory shock |
| PMC8327834 | Pembrolizumab-induced cytokine release syndrome | Drug-induced refractory hypotension |
| PMC8731279 | Anaphylactic Reactions Caused by Nafamostat Mesylate | Procedure-related drug-induced hypotension |
| PMC7522583 | Primary myelofibrosis with spontaneous post-op bleeding | Post-operative refractory hypotension with hemoglobin drop |

---

## Scoring Guidance for Evaluator

| Field | Pass Criteria |
|---|---|
| final_diagnosis | Semantically matches "intramural haematoma" or accepted variants |
| specialist_findings | All 3 domains present with total_cases = 500, relevant_count ≥ 3 |
| cardiac_supporting_cases | ≥ 3 PMCIDs from cardiac_cases.jsonl with verbatim excerpts; ≥ 2 of 3 gold PMCIDs |
| vascular_supporting_cases | ≥ 3 PMCIDs from vascular_cases.jsonl with verbatim excerpts; ≥ 2 of 5 gold PMCIDs |
| systemic_supporting_cases | ≥ 3 PMCIDs from systemic_cases.jsonl with verbatim excerpts; ≥ 2 of 5 gold PMCIDs |
| cardiac_case_stats | total_cases = 500, relevant_count in [3, 50], gold PMCID overlap ≥ 2 |
| vascular_case_stats | total_cases = 500, relevant_count in [3, 80], gold PMCID overlap ≥ 2 |
| systemic_case_stats | total_cases = 500, relevant_count in [3, 100], gold PMCID overlap ≥ 2 |
| cross_domain_evidence_matrix | intramural_haematoma.cardiac = "supports"; pericardial_tamponade.cardiac = "contradicts" |
| most_discriminating_case | PMCID is one of PMC9364049, PMC9332897, PMC7954273; source is cardiac_cases.jsonl |
| weakest_domain | Consistent with agent's own relevant_count (domain with fewest) |
| excluded_diagnoses | ≥ 4 of 6 required exclusions present |
| diagnostic_approach | Mentions three domains and case review; does not claim keyword matching |
| confidence | "high" or "medium" |

---

## Data Source

This case is derived from PMC7042146 via the `zou-lab/MedCaseReasoning` dataset (HuggingFace). The three domain databases (cardiac, vascular, systemic) each contain 500 cases sampled from the same dataset.
