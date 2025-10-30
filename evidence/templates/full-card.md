---
id: {{ card_id }}
created_at: {{ created_at }}
updated_at: {{ updated_at }}
status: {{ status }}
analyst: {{ analyst }}
---

# {{ title }}

## Claim
{{ claim_statement }}

### Scope
- **Primary Passage:** {{ primary_passage }}
- **Related Passages:** {{ related_passages | join(", ") }}
- **Doctrinal Scope:** {{ doctrinal_scope }}
- **Confidence:** {{ confidence }}

## Evidence Summary
{{ evidence_summary }}

### Key Excerpts
{% for excerpt in excerpts %}
- {{ excerpt.reference }} — {{ excerpt.snippet }}
{% endfor %}

### Source Provenance
| Source | Type | Publication | Notes |
| --- | --- | --- | --- |
{% for source in sources %}| {{ source.title }} | {{ source.type }} | {{ source.publication }} | {{ source.notes }} |
{% endfor %}

## Analysis
- **Support Level:** {{ support_level }}
- **Counterpoints:** {{ counterpoints }}
- **Risk Factors:** {{ risk_factors }}

## Recommended Actions
1. {{ action_primary }}
2. {{ action_secondary }}

## Tags
{{ tags | join(", ") }}

## Appendices
{% for appendix in appendices %}
### {{ appendix.title }}
{{ appendix.body }}
{% endfor %}
