# Pass 3: Virtual Re-implementation - Detailed Guidance

## Purpose

Test deep understanding by having the learner mentally reconstruct the paper's core contribution. Identify and challenge every assumption. This pass separates surface familiarity from true comprehension.

## The Re-implementation Mindset

The learner should approach this as: "If I had to recreate this paper's core result, could I?"

This doesn't mean implementing code. It means:
- Understanding the logical structure
- Knowing why each piece exists
- Recognizing dependencies and assumptions
- Anticipating what would break if pieces changed

## Core Questions

### Starting Point

```
AI: If you had to recreate this paper's core contribution from scratch,
    where would you start?

[Probe their answer]

AI: Why that starting point? What makes it foundational?
```

### Building the Structure

Work through the paper's logic step by step:

| Phase | Questions |
|-------|-----------|
| **Foundation** | "What's the key insight that makes this work possible?" |
| **Architecture** | "What are the main components? How do they connect?" |
| **Mechanism** | "Walk me through how [core process] actually works" |
| **Training** | "How does the model learn? What's the objective?" |
| **Evaluation** | "How do they know it works? What are they measuring?" |

### Probing Depth

For each answer, go deeper:

- "Why did they choose that approach?"
- "What alternatives exist? Why weren't they chosen?"
- "What would happen if we removed this component?"
- "What's the simplest version that would still work?"

## Assumption Identification

### Types of Assumptions

| Type | Example | Probe |
|------|---------|-------|
| **Data** | "Assumes large training corpus" | "What if data were scarce?" |
| **Compute** | "Assumes GPU availability" | "Could this run on limited hardware?" |
| **Domain** | "Assumes English text" | "Would this work for [other domain]?" |
| **Theoretical** | "Assumes IID samples" | "What if distribution shifts?" |
| **Practical** | "Assumes clean inputs" | "What about noisy real-world data?" |

### Uncovering Hidden Assumptions

```
AI: What assumptions does this approach rely on?

Learner: [Lists some]

AI: Good. Are there assumptions that aren't stated explicitly?
    Think about what has to be true for this to work.

Learner: [Considers]

AI: What about [specific hidden assumption]? The paper doesn't
    address it directly, but their approach seems to assume...
```

### Challenging Assumptions

For each assumption identified:

```
AI: You identified [assumption]. What happens if it's wrong?

Learner: [Considers impact]

AI: Does the paper address this? What do they say?

Learner: [Checks/recalls]

AI: Does their response satisfy you? What would make it stronger?
```

## Weakness Identification

### Probing Questions

- "Where is the authors' argument weakest?"
- "What would a skeptical reviewer attack?"
- "Where do the authors hedge their claims?"
- "What limitations do they acknowledge vs. ignore?"
- "If you had to find a counterexample, where would you look?"

### Common Weakness Categories

| Category | Example Questions |
|----------|-------------------|
| **Generalization** | "Will this work beyond their specific setup?" |
| **Scalability** | "What happens at 10x or 100x scale?" |
| **Reproducibility** | "Could someone replicate this from the paper alone?" |
| **Comparison** | "Did they compare against the right baselines?" |
| **Metrics** | "Do their metrics capture what actually matters?" |

## Strength Recognition

Balance criticism with recognition:

- "Where is the argument most convincing?"
- "What's the strongest evidence they present?"
- "What would be hardest for a competitor to replicate?"
- "Where are the authors most confident, and is it justified?"

## Dialogue Example

```
AI: Let's virtually re-implement. If you had to recreate the
    Transformer's self-attention from scratch, what would you need?

Learner: You need queries, keys, and values computed from the input...

AI: Good. Why all three? What role does each play?

Learner: Queries ask what to look for, keys say what's available,
    values are what you actually retrieve...

AI: Right. Now, what assumption underlies the dot-product attention?

Learner: That similarity in embedding space means relevance?

AI: Exactly. When might that assumption break down?

Learner: If the embedding space doesn't capture the right notion
    of similarity for the task...

AI: What does the paper do to address this?

Learner: They use multiple heads to capture different similarity notions...

AI: Does that fully solve the problem? What could still go wrong?
```

## Completion Criteria

Pass 3 is complete when the learner can:
1. Walk through the paper's logic from first principles
2. Identify explicit and hidden assumptions
3. Articulate strengths and weaknesses
4. Defend or critique specific design choices
5. Explain what would break under different conditions

**Transition phrase:** "You could explain and defend this paper now. Ready to test that with a discussion simulation?"
