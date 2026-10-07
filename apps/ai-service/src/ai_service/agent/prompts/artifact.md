<!-- version: 2 -->
Create the artifact described by the skill below, using ONLY facts from the sources.

# Skill
{{skill}}

# Requirements
- Every `CitedText` must have `source_ids` with at least one sid of a supporting source. Do NOT write `[S#]` markers inside any text — citations go only in `source_ids`.
- State facts exactly as the cited source says them (numbers, usage instructions, results); hooks may paraphrase approved claims but must not add new facts.
- Publishable fields ({{publishable}}) will be used in real ads: they must comply with every compliance rule — no prohibited wording at all, not even negated.
- If the user's request contains a claim that violates a rule, do NOT use it: record it in `compliance_notes` (requested claim, rule id, explanation citing the compliance policy source, and 2–3 compliant alternatives), and list the prohibited wording in `do_not_say`.
- Include every required phrase that applies to the product (e.g. SPF usage statement) verbatim in `mandatory_inclusions`.
- If the KB lacks something the brief needs, say so in `open_questions` instead of inventing it.
- Write in the user's language unless the user asks otherwise; ad copy may stay in English for a US audience.

{{coverage}}

{{sources}}
