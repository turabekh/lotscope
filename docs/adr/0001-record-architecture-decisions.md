# 1. Record architecture decisions

Date: 2026-06-27

## Status

Accepted

## Context

LotScope is built as a modular monolith with strict boundaries and several decisions that have lasting impact (datastore choices, the verdict contract, ingestion strategy, auth model, tiling approach). Per `CLAUDE.md` §4, decisions with lasting impact must be recorded so the rationale survives beyond the diff and beyond any single contributor.

## Decision

We use Architecture Decision Records, one per decision, stored in `docs/adr/` as `NNNN-title.md` and numbered sequentially. Each ADR follows the structure: **Context → Decision → Consequences**, with a Status field (Proposed / Accepted / Superseded).

A change that introduces or alters an architectural decision adds or supersedes an ADR in the same PR. Superseding ADRs reference the ones they replace.

## Consequences

- Rationale for structural choices is discoverable and reviewable.
- Reversing a decision is explicit (a new ADR superseding the old), not silent.
- Small, non-architectural changes do not need an ADR — this is reserved for lasting decisions.
