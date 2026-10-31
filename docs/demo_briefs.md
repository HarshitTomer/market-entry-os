# Demo briefs — unseen inputs judges can try

These are **not** hard-coded: the parser, search, scoring and exports are
all generic. Paste any one of these (or invent your own) and the mission
must finish with no further prompts.

## 1. Spec example (baseline)
> We sell cybersecurity compliance software for financial technology companies.
> Evaluate entry into the UK fintech market. Focus on companies with 50-500 employees.
> Estimate using a £12,000 annual contract value; identify competitors and buyer roles;
> produce a ranked shortlist.

Check: UK country filter, 50–500 headcount, GBP 12,000 sizing, buyers in compliance/security roles.

## 2. Unseen: healthtech, India
> We sell appointment scheduling software for healthcare clinics. Evaluate entry into
> the Indian healthcare market. Focus on companies with 50-200 employees.
> Estimate using a ₹60,000 annual contract value.

Check: India filter, healthcare industry (not "software"), INR sizing, no invented USD figure.

## 3. Unseen: logistics, Germany
> We sell logistics software for manufacturing companies. Evaluate entry into the
> German manufacturing market. Focus on companies with 100-1000 employees.

Check: Germany filter, Manufacturing industry (not "software"), and — because no
ACV is given — **no monetary estimate at all** in the report.

## 4. Edge case: no buyers, no ACV, tiny universe
> We sell niche software for energy companies in Ireland. Focus on companies with
> 500-5000 employees.

Check: mission completes with warnings, buyer_not_found where applicable,
and empty CSVs that are still valid files — not a crash, not fabricated companies.
