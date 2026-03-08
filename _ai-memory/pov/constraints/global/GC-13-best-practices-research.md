---
id: GC-13
name: ALWAYS Research Best Practices Before Dispatching for New Tech or After Failed Fix
category: Quality
severity: HIGH
---

# GC-13: ALWAYS Research Best Practices Before Dispatching for New Tech or After Failed Fix

## Constraint

Parzival MUST ensure current best practices exist in the knowledge base (Qdrant conventions collection) before dispatching agents to work with technologies, and MUST research best practices when a fix fails on the first attempt.

## When This Constraint Applies

### Mandatory Triggers

1. **Project Initialization** (new or existing): Research best practices for EVERY major technology in the confirmed stack. Minimum: primary language/framework + primary data store. This must happen BEFORE Discovery begins.

2. **New Technology or Pattern**: When a story introduces a technology, framework, or architectural pattern not previously used in the project, research best practices BEFORE dispatching DEV.

3. **Failed Fix (Pass 2+)**: When a review cycle fix does not resolve on the first attempt, research the specific failing pattern BEFORE sending correction instructions. A second pass means the knowledge base may lack current guidance.

4. **Security-Sensitive Work**: When a story involves authentication, authorization, encryption, data handling, or external API integration, ALWAYS verify current security best practices — regardless of database state.

5. **Phase Entry (Architecture/Planning)**: Assess whether the technologies involved have current best practices in the database. Research any gaps before agents begin phase work.

### Acceptable Skip Conditions

- Minor bug fix in well-researched technology (best practices confirmed <30 days ago)
- Purely documentation or configuration changes
- Best practices for the specific technology were researched earlier in the same session

## Mechanism

Run `/aim-best-practices-researcher` with the specific technology or pattern. The skill:
1. Checks Qdrant conventions collection first (avoids redundant research)
2. If found with score >0.7 and <6 months old, uses existing — no web research
3. If missing or stale, performs web research for 2024-2026 sources
4. Stores findings to both file (`oversight/knowledge/best-practices/BP-XXX.md`) and Qdrant
5. Evaluates if findings warrant a reusable skill

## Why This Matters

Best practices in Qdrant are the foundation for agent quality. DEV agents receive these via Tier 2 context injection — they don't need to be told to follow them, the injection system delivers relevant practices automatically. Without current practices in the database, agents build with outdated patterns, leading to:
- More review cycle iterations (fixing avoidable issues)
- Security vulnerabilities from outdated patterns
- Architecture decisions based on superseded approaches
- Wasted time on patterns the industry has moved past

Research investment is amortized: done once, used by every agent for the project's lifetime.

## Violation Response

If Parzival dispatches an agent without best practices research when a trigger condition is met:
1. STOP the current instruction
2. Research the relevant best practices NOW
3. Update the instruction to include relevant findings
4. Resume dispatch

If Parzival sends a correction instruction after a failed fix without researching:
1. Research the specific failing pattern
2. Include findings in the correction instruction
3. Continue the review cycle with enriched context
