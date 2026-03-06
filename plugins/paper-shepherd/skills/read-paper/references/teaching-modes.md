# Teaching Modes - Detailed Guidance

## Purpose

Adapt teaching approach in real-time based on learner responses. The goal is keeping the learner in flow - challenged but not stuck, engaged but not overwhelmed.

## The Two Modes

### Socratic Mode

**When to use:** Learner is grasping concepts, showing confidence, making connections.

**Approach:**
- Ask questions that lead to discovery
- Never give answers directly
- Build on learner's responses
- Challenge them to go deeper

**Example patterns:**
- "What makes you say that?"
- "Why do you think they chose X over Y?"
- "What would happen if..."
- "How does that connect to..."
- "What's the implication of that?"

**Benefits:**
- Deeper retention (self-discovered knowledge sticks)
- Builds reasoning skills
- Reveals actual understanding vs. surface familiarity
- More engaging for learner

### Direct Instruction Mode

**When to use:** Learner is struggling, frustrated, lacks foundational knowledge.

**Approach:**
- Provide clear explanations
- Start with familiar analogies
- Build up complexity gradually
- Verify understanding before moving on

**Example patterns:**
- "Let me ground this. [Concept] is like..."
- "The key insight is..."
- "In simple terms, this means..."
- "Think of it this way..."
- "Does that land? Can you restate it?"

**Benefits:**
- Prevents learner from getting stuck
- Builds necessary foundation
- Maintains forward momentum
- Reduces frustration

## Mode Switching Signals

### Switch to Socratic When:

| Signal | Example |
|--------|---------|
| Quick, confident answers | "Yeah, it's because of X" |
| Learner asks deeper questions | "But why did they need multiple heads?" |
| Makes unprompted connections | "Oh, this is like what we saw in..." |
| Shows genuine curiosity | "I wonder what would happen if..." |
| Correctly anticipates | "I bet the next step is..." |

### Switch to Direct When:

| Signal | Example |
|--------|---------|
| Long pauses, hesitation | "I'm not sure..." |
| Surface-level answers | "I guess it's just better?" |
| Repeated confusion | "Wait, I still don't get it" |
| Signs of frustration | "This doesn't make sense" |
| Fundamental gaps | "What's a neural network?" |
| Nodding without substance | "Yeah, yeah, I see" (but can't explain) |

## Adaptive Calibration

### Within a Single Exchange

```
AI: Why do you think they used layer normalization?

Learner: Um... to normalize the layers?

[Signal: Tautological answer -> Switch to direct]

AI: Let me ground this. Training deep networks is unstable - small
    changes early cascade into big changes later. Normalization
    keeps values in a stable range. In Transformers specifically,
    they normalize after each sub-layer. What do you think the
    alternative would look like?

Learner: Without it, you'd get values that explode or vanish?

[Signal: Correct intuition -> Can return to Socratic]

AI: Exactly. So when they say "residual connection + layer norm,"
    what's the residual connection adding to this picture?
```

### Across a Session

Track patterns over the conversation:

| Pattern | Adaptation |
|---------|------------|
| Consistently strong | Increase challenge, go deeper |
| Strong then flagging | Check for fatigue, offer break |
| Struggling then improving | Foundation was the gap, stay supportive |
| Inconsistent | Different concept strengths - adapt per topic |

## The Flow Zone

### Goal: Keep Learner in Flow

Flow state characteristics:
- Challenge matches skill level
- Clear goals and progress
- Immediate feedback
- Deep engagement

### Too Easy (Boredom)

**Signs:** Short, dismissive answers; rushing; disengagement

**Response:** Increase challenge
- Ask "why" and "what if" more
- Introduce edge cases
- Challenge assumptions more aggressively

### Too Hard (Frustration)

**Signs:** Long pauses; repeated confusion; emotional responses

**Response:** Reduce difficulty
- Switch to direct instruction
- Break into smaller pieces
- Provide more scaffolding
- Acknowledge the difficulty

### Just Right (Flow)

**Signs:** Engaged responses; building on previous answers; asking good questions

**Response:** Maintain calibration
- Continue current approach
- Gently increase challenge over time
- Celebrate progress subtly

## Handling Specific Situations

### Learner is Wrong

**Don't:** "No, that's incorrect."

**Do:** Ask questions that reveal the gap.

```
Learner: The key contribution is the attention mechanism.

AI: Attention existed before this paper. What specifically does
    this paper do differently with attention?

Learner: Oh... they use only attention, without RNNs?

AI: Right. So what's the actual contribution?
```

### Learner is Partially Right

**Don't:** "Yes, but also..."

**Do:** Acknowledge and extend.

```
Learner: It's faster because there's no sequential processing.

AI: That's a key part of it. What enables that parallelization
    that wasn't possible before?
```

### Learner is Stuck

**Don't:** Long silence or repeated questioning.

**Do:** Offer a hint, then explain if needed.

```
AI: What role does positional encoding play?

Learner: I'm not sure...

AI: Think about what attention alone can see. If you shuffle
    the input words, does attention know?

Learner: Oh - it can't tell position!

AI: Right. So positional encoding...

Learner: Adds that information back in.
```

### Learner Knows More Than Expected

**Don't:** Slow them down with basics.

**Do:** Skip ahead, go deeper.

```
Learner: I know transformers well. I've implemented them.

AI: Great. Then let's focus on assumptions and limitations.
    Where do you think the architecture is weakest?
```

## Energy Management

### Signs of Fatigue

- Shorter answers over time
- Increasing errors
- Reduced engagement
- Direct questions about "how much more"

### Response to Fatigue

```
AI: We've covered a lot. Want to pause here and pick up
    with Pass 3 later? Or push through?

[Let learner decide]
```

### Session Pacing

| Pass | Typical Energy |
|------|----------------|
| Pass 1 | High - fresh engagement |
| Pass 2 | Medium - deep work |
| Pass 3 | Variable - can be intense |
| Discussion | High - performance mode |

Consider suggesting breaks between passes for dense papers.
