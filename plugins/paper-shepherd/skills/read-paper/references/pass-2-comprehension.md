# Pass 2: Comprehension - Detailed Guidance

## Purpose

Fill knowledge gaps identified in Pass 1. Make the unfamiliar familiar. This pass builds the conceptual foundation needed for deep understanding.

## Gap Identification

### Sources of Gaps

From Pass 1 discussion, identify:
- Concepts the learner mentioned uncertainty about
- References the learner didn't recognize
- Technical terms that caused hesitation
- Assumptions the learner couldn't fully evaluate
- Figures or diagrams that weren't clear

### Prioritization

Not all gaps matter equally. Prioritize by:
1. **Critical path:** Does understanding this unlock the main contribution?
2. **Frequency:** Does this concept appear repeatedly?
3. **Foundation:** Is this prerequisite knowledge for other concepts?

Skip gaps that are:
- Tangential to main contribution
- Nice-to-know but not essential
- Too deep for current goals

## Reference Exploration

### Adaptive Approach

When a reference comes up:

```
AI: You mentioned the authors cite [Smith 2019] for their baseline.
    What do you know about that work?

[If learner knows]: Great, how does it relate to what this paper does differently?

[If learner doesn't know]: Want a 2-sentence context, or prefer to
    work through what you can infer from how it's cited here?
```

### Reference Context Levels

Provide context at the level needed:

| Learner State | Provide |
|---------------|---------|
| Never heard of it | 2-sentence summary: what it did, why it mattered |
| Heard of it, fuzzy | 1-sentence reminder + relationship to current paper |
| Knows it well | Skip to comparison with current paper |

### Key Questions for References

- "How does [reference] relate to the current paper's approach?"
- "What did [reference] do that this paper builds on?"
- "What limitation of [reference] does this paper address?"
- "Are the authors positioning themselves against [reference] or extending it?"

## Figure and Diagram Analysis

### Approach

For each key figure:

```
AI: Let's look at Figure 3. What's it showing you?

Learner: [Interprets]

AI: [If correct] Good. What's the key takeaway for the paper's argument?
    [If partially correct] You've got part of it. What about [aspect]?
    [If incorrect] Look at the axis labels again. What do X and Y represent?
```

### Common Figure Types

| Type | Key Questions |
|------|---------------|
| Architecture diagram | "Walk me through the data flow" |
| Results graph | "What comparison is being made? Who wins?" |
| Ablation study | "What does removing X tell us?" |
| Example/visualization | "Why did they choose this example?" |

## Concept Explanation

### When Learner is Stuck

If learner explicitly asks for explanation:

1. **Offer hint first:** "Before I explain, what's your intuition?"
2. **Provide grounding:** Start with familiar analogy
3. **Build up:** Layer complexity gradually
4. **Verify:** "Does that land? Can you restate it?"

### Example Dialogue

```
Learner: I don't understand attention mechanisms.

AI: Before I explain, what's your intuition about what "attention"
    might mean in this context?

Learner: Something about focusing on important parts?

AI: Exactly right intuition. In neural networks, attention is a way
    for the model to learn which parts of the input matter most for
    each part of the output. Instead of treating all input equally,
    it assigns weights. Does that connect with what you're seeing
    in the paper?

Learner: Kind of, but how does it actually work?

AI: Think of it like a search. You have a query (what you're looking for),
    keys (labels on information), and values (the information itself).
    Attention computes how well each key matches your query, then
    retrieves a weighted combination of values. In the paper, where
    do you see this query-key-value structure?
```

## Progress Tracking

### Signs of Growing Understanding

- Learner asks more specific questions (not "what is X" but "why X instead of Y")
- Learner makes connections between concepts unprompted
- Learner correctly anticipates where a concept will appear in the paper
- Learner can explain concepts back in their own words

### Signs More Work Needed

- Learner nods along but can't restate
- Questions stay at surface level
- Learner avoids engaging with specific details
- Confusion persists after explanation

## Completion Criteria

Pass 2 is complete when:
1. Key references are understood in context
2. Technical concepts no longer cause hesitation
3. Figures and diagrams are interpretable
4. Learner can explain the paper's approach without hedging

**Transition phrase:** "The machinery is clear now. Ready to try rebuilding it in Pass 3?"
