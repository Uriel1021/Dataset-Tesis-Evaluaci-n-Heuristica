# Nielsen Silver Annotation — silver_v1

You are evaluating one concrete web-interface task execution.

Evaluate ONLY the evidence supplied for this instance.
Do not infer behavior that is not observable.

Targets:
- H1: Visibility of system status
- H4: Consistency and standards
- H5: Error prevention
- H6: Recognition rather than recall

For each heuristic return:
- label: 1, 0, or null
- confidence: 0.0 to 1.0
- evidence: concise description of the observable evidence supporting the label

Rules:
1. label=1 only when an observable violation is supported.
2. label=0 only when the heuristic is applicable and sufficient evidence supports absence of a violation in the evaluated flow.
3. label=null when the heuristic is not assessable from the evidence.
4. Do not use absence of evidence as a negative label.
5. Do not invent pages, states, controls, errors, messages, delays, or user actions.
6. Judge the evaluated instance, not the general reputation or expected design of the site.
7. Do not use or request computed feature values, thresholds, model predictions, or prior labels.

Return JSON only:
{
  "H1": {"label": 0|1|null, "confidence": 0.0-1.0, "evidence": "..."},
  "H4": {"label": 0|1|null, "confidence": 0.0-1.0, "evidence": "..."},
  "H5": {"label": 0|1|null, "confidence": 0.0-1.0, "evidence": "..."},
  "H6": {"label": 0|1|null, "confidence": 0.0-1.0, "evidence": "..."}
}
