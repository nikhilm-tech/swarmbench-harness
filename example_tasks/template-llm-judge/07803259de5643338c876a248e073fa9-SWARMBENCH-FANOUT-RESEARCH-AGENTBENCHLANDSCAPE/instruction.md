You are conducting a structured survey of agent benchmark papers. Search the web (arxiv, Google Scholar, or Semantic Scholar) for each of the following 11 benchmark papers. Read each paper and extract the specific fields listed below.

Papers to research:
1. API-Bank (Li et al., 2023)
2. ACEBench (Chen et al., 2025)
3. τ-bench (Yao et al., 2024)
4. τ²-bench (Barres et al., 2025)
5. WorkArena (Drouin et al., 2024)
6. WorkArena++ (Boisvert et al., 2024)
7. ITBench (Jha et al., 2025)
8. WorkBench (Styles et al., 2024)
9. TheAgentCompany (Xu et al., 2024)
10. CRMArena (Huang et al., 2025)
11. CRMArena-Pro (Huang et al., 2025)

For EACH paper, extract these 6 fields:
- benchmark_name: Short name only — do not include paper subtitle. Report only the benchmark identifier (e.g., report "ACEBench" not "ACEBench: Who Wins the Match Point in Tool Usage?", report "WorkBench" not "WorkBench: a Benchmark Dataset for...").
- num_domains: Number of distinct task domains, content categories, stakeholder personas, or job departments the benchmark covers. Stakeholder roles/personas (e.g., service agent, analyst, manager) and job departments (e.g., SDE, HR, Finance) count as valid domain categories. If the paper organises tasks only by pure cognitive/skill dimensions (e.g., planning, retrieval, reasoning, memorization) with no content domain separation, report "not provided".
- num_tasks: Total number of tasks in the benchmark. For benchmarks with multiple domains, report the combined total across all domains.
- has_human_task_curation (boolean): Whether tasks or evaluation data were manually created, annotated, or curated by humans.
- has_refusal_ability (boolean): Whether the benchmark includes tasks where the agent must refuse, reject, or flag unsolvable/infeasible/unanswerable requests. This includes: tasks requiring detection of missing/erroneous parameters, infeasible task identification, non-answerable query detection, policy-based refusal, and transfer-to-human scenarios.
- has_human_plans (boolean): Whether the paper provides human-authored step-by-step action plans, solution sequences, or oracle action traces as ground truth. This includes: Playwright oracle functions that solve tasks step-by-step, annotated API call chains, ground-truth database write action sequences, and solution functions specifying ordered tool calls. Set to false if evaluation uses only checkpoint-based scoring of environment states (pass/fail milestones) or exact-match of final answers without any reference to intermediate action sequences.

For EACH field you extract (except benchmark_name), you must also provide a "statement_from_the_paper" field containing an array of 1-3 exact verbatim quotes from the paper that justify your extracted value. Field name format: <field_name>_statement_from_the_paper

You must search for and actually read each paper. Do not guess values. Write the final result to output/output.json.


---

## Output Instructions

Write your final answer to `/logs/agent/output.json` in this exact JSON format:

```json
{
  "benchmarks": [
    {
      "benchmark_name": "<str>",
      "num_domains": "<int>",
      "num_domains_statement_from_the_paper": [
        "<str>"
      ],
      "num_tasks": "<str>",
      "num_tasks_statement_from_the_paper": [],
      "has_human_task_curation": "<bool>",
      "has_human_task_curation_statement_from_the_paper": [
        "<str>"
      ],
      "has_refusal_ability": "<bool>",
      "has_refusal_ability_statement_from_the_paper": [],
      "has_human_plans": "<bool>",
      "has_human_plans_statement_from_the_paper": [
        "<str>"
      ]
    }
  ]
}
```

Do not write anything else to that file.