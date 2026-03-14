# Phase Map Format

Phase maps define the learn-build spiral for a single project. Each project gets one phase map at `docs/phases/project-N-<name>.md` in the learning area directory.

## Template

```markdown
# Project N: <Name>

**Domain:** <e.g., game/puzzle, robotics, LLM alignment>
**Estimated duration:** <e.g., ~1.5 weeks at 10 hrs/week>
**Tech stack:** <e.g., Python, NumPy, PyTorch>

## Prerequisites

What the learner should know coming in. Reference specific prior projects.

- From Project N-1: <specific concepts and skills>
- General background: <assumed knowledge>

## Phase 1: <Concept Name>

### Learn
- **Concepts** (ordered, each builds on prior):
  1. Concept A -- intuition/analogy to introduce it
  2. Concept B -- builds on A
  3. Concept C -- builds on B
- **Math:** Key equations with notation explained
- **Hand exercise:** A concrete exercise the learner works through before coding
  - Must be doable on paper or in their head
  - Should directly connect to what they will implement

### Build
- **Goal:** What to implement in this phase
- **Design decisions:** Questions to pose to the learner ("How should we represent X?")
- **Skeleton scope:** What the professor provides vs what the learner writes
- **Verification:** How to confirm it works AND ties back to theory
  - Compare code output to hand exercise result
  - Or: predict behavior, then observe

## Phase 2: <Concept Name>
(same structure)

## Phase N: ...
(same structure)

## Synthesis
- **Experiments:** What to run and compare
- **Reflection questions:** What did you learn? When would you use each approach?
- **Writeup topic:** Blog post or README focus
- **Bridge to next project:** What limitations of this project motivate the next one?
```

## Constraints

1. **Learn items are ordered.** Each concept within a phase builds on the previous one.
2. **Every Learn has at least one hand exercise.** No exceptions. The learner must work through something manually before writing code.
3. **Every Build has a verification step.** The verification must connect back to theory, not just "does it run."
4. **Predict-then-observe where possible.** Ask the learner to predict behavior before running code. This is the strongest learning signal.
5. **Synthesis bridges to the next project.** The final phase should make the learner feel the limitations that the next project addresses.
6. **3-6 phases per project.** Fewer than 3 means the project is too simple. More than 6 means it should be split into two projects.
7. **Each phase is 1-3 sessions.** A session is roughly 1-2 hours. If a phase would take more than 3 sessions, split it.

## Calibration

When generating a phase map for Project 2+, read:
- `docs/learner-profile.md` for strengths, growth areas, preferences
- `docs/retros/project-(N-1)-retro.md` for recent retrospective
- Previous conversation history for struggle/breakthrough patterns

Adjust accordingly:
- **Growth areas** get more hand exercises, smaller steps, and concrete examples before formulas
- **Strengths** get larger build chunks and more "you propose, I push back" interactions
- **Preferences** shape the teaching style (e.g., "prefers wrong approach first" means show naive solution before optimal)
