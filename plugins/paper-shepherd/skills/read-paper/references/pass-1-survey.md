# Pass 1: Orientation and Guided Tour - Detailed Guidance

## Purpose

Build foundational understanding through progressive disclosure. Start with the big picture, establish prerequisites, then walk through section-by-section with frequent check-ins.

**Target audience:** Senior CS undergrad with no domain-specific knowledge.

## Part A: Orientation

### Step 1: Big Picture

After reading the paper, provide 2-3 sentences that answer:
- What problem does this paper address?
- What's the one-sentence answer/contribution?

**Good example:**
> "This paper is about finding a security vulnerability in China's Great Firewall. The researchers discovered they could trick the firewall into revealing its internal memory contents - similar to the Heartbleed bug that affected much of the internet in 2014."

**Bad example (too technical, no context):**
> "This paper presents Wallbleed, a memory disclosure vulnerability in the GFW's DNS injection subsystem that leaks up to 125 bytes per query via malformed packets."

The bad example assumes the reader knows what GFW, DNS injection, and memory disclosure mean.

### Step 2: Prerequisite Concepts

Identify 3-5 things the reader needs to understand before the paper makes sense.

**Selection criteria:**
- Would a smart undergrad know this? If no, include it.
- Is this term used repeatedly in the paper? If yes, include it.
- Would misunderstanding this derail comprehension? If yes, include it.

**Analogy-First Format:**

For each concept:
1. Start with an analogy or intuitive explanation
2. Only add technical precision if needed for the paper

**Example transformation:**

| Concept | Bad (Technical First) | Good (Analogy First) |
|---------|----------------------|---------------------|
| DNS | "DNS is a hierarchical distributed naming system that maps domain names to IP addresses using UDP port 53" | "DNS is like a phone book for the internet. You give it a name (google.com), it gives you a number (142.250.80.46) that computers use to find each other." |
| Memory safety | "A memory safety vulnerability occurs when software accesses memory outside its allocated bounds" | "Imagine a librarian who, when you ask for book #5, accidentally also hands you books #6, #7, and #8. The software meant to give you one piece of data accidentally gives you extra data from nearby memory." |
| Firewall | "A firewall is a network security device that monitors and filters incoming and outgoing network traffic based on security policies" | "A firewall is like a security guard checking every package entering or leaving a building, blocking anything that looks suspicious or is on the banned list." |

### Step 3: Check-in

Always pause after orientation:

> "Does this framing make sense? Anything unclear before we start walking through the paper?"

**Wait for response.** Do not proceed until learner confirms or asks clarifying questions.

**If learner asks a question:** Answer it thoroughly, using the same analogy-first approach. Then check in again.

---

## Part B: Guided Tour

### Section-Level Summaries (Not Paragraph-Level)

**Critical change from old approach:** Summarize at the section level, not paragraph level. Paragraph-by-paragraph overwhelms. Section-level provides digestible chunks.

**For each section:**

1. **Summary** (50-100 words)
   - What does this section say?
   - Use plain language
   - Define new terms inline using analogies

2. **Key takeaway** (1 sentence)
   - The one thing to remember from this section

3. **Check-in**
   - "Does this make sense?"
   - "Anything unclear before we continue?"

**Example:**

> **Section 3: Methodology**
>
> The researchers sent millions of specially-crafted DNS requests from computers outside China to servers inside China. These requests were malformed in a specific way - they claimed to be longer than they actually were. When the Great Firewall intercepted these requests and tried to respond, it read past the end of the request into adjacent memory, then accidentally included that extra data in its response.
>
> **Key takeaway:** The vulnerability is triggered by lying about packet length, causing the firewall to read and echo back memory it shouldn't.
>
> Does this make sense? Any questions about how the attack works?

### Progressive Layering for Technical Terms

When a term first appears, use Layer 1 (analogy). Only go deeper if:
- Learner asks
- Next section requires it
- We're in Pass 2/3

**Layer 1 - Analogy (default):**
> "DNS poisoning is like someone sneaking into the phone book and changing the number for 'Bank of America' to a scammer's number."

**Layer 2 - Mechanics (on request):**
> "Specifically, the attacker injects a fake DNS response that arrives before the real one, causing your computer to cache the wrong IP address."

**Layer 3 - Nuance (Pass 2/3 only):**
> "The attack works because DNS responses are matched only by transaction ID and port number. If an attacker can guess or brute-force these values..."

---

## Part C: Weaving in the 5 Cs

### When to Introduce Each C

| C | Natural Point | Example Prompt |
|---|---------------|----------------|
| **Category** | After intro/abstract | "Based on what we've seen so far, what type of paper do you think this is?" |
| **Context** | After background section | "What problem existed before this paper? What were people doing about it?" |
| **Contributions** | After main results | "What's the new thing this paper brings to the field?" |
| **Correctness** | After methodology | "What assumptions are the authors making? Do they seem valid?" |
| **Clarity** | Throughout or at end | "Was that section clear to you? What would have helped?" |

### The Learner Proposes, AI Probes

**Pattern:**
```
AI: [Presents section summary, then asks about relevant C]
Learner: [Proposes answer]
AI: [Probes] "What makes you say that?" / "How does it differ from X?"
Learner: [Refines]
AI: [Confirms or pushes further]
```

**Probing questions by C:**

**Category:**
- "What makes you categorize it that way?"
- "How does it differ from [alternative type]?"
- "What would you expect to find in the methods section given this category?"

**Context:**
- "What problem existed before this paper?"
- "What's the relationship between this work and [key citation]?"
- "Why weren't previous approaches sufficient?"

**Correctness:**
- "What assumptions did you notice?"
- "Are there hidden assumptions you might have missed?"
- "What would invalidate the results?"

**Contributions:**
- "Is that contribution truly new, or incremental improvement?"
- "What would the field lose if this paper didn't exist?"
- "What's the single strongest contribution?"

**Clarity:**
- "What specifically confused you?"
- "Were there sections that felt unnecessarily complex?"
- "How would you restructure this?"

---

## Part D: Adaptive Granularity

### Start Coarse

Begin with section-level summaries. This is the right default.

### Detect Confusion

Watch for these signals:
- Explicit: "I don't understand", "What does X mean?"
- Implicit: Questions about something already explained
- Misconceptions revealed in learner's responses
- Long silences after complex sections

### Respond to Confusion

When confusion detected, do NOT just repeat. Instead:

1. **Try a different analogy**
   - If the phone book analogy for DNS didn't work, try "DNS is like asking a friend for someone's address"

2. **Break into smaller pieces**
   - If a section was too dense, break it into 2-3 sub-sections

3. **Connect to something they know**
   - "You know how your browser shows a padlock for secure sites? That's related to..."

4. **Ask what specifically is unclear**
   - "Which part lost you - the packet structure or the memory reading?"

### Speed Up When Appropriate

If learner is following easily:
- Combine shorter sections
- Move faster through familiar material
- Ask deeper "why" and "what if" questions
- Skip to the next C earlier

---

## Completion Criteria

Orientation and Guided Tour (formerly "Pass 1") is complete when:

1. Learner understood the big picture and prerequisites
2. All major sections have been walked through
3. Learner has articulated all 5 Cs at natural points with justification
4. No major confusion signals remain unaddressed

**Transition phrase:** "We've walked through the whole paper and you've got a solid grasp of the 5 Cs. Ready to dig deeper into any areas that felt fuzzy?"
