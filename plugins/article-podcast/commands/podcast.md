---
name: podcast
description: Convert a URL into a podcast episode
argument-hint: <url> [options]
allowed-tools:
  - Bash
  - Read
  - Write
---

Convert the provided URL into a podcast episode. Follow the article-podcast skill workflow:

1. Fetch and classify the article using the scriptgen module
2. Generate a podcast transcript in the appropriate format (interview, discussion, or narrator)
3. Write the transcript to a temporary file
4. Run the synthesis and publishing pipeline via generate.py with --transcript-file
5. Report the results (title, duration, backend, audio URL) to the user

Parse the user's input for:
- **URL** (required): The article/paper/blog post URL
- **Format override**: "interview", "discussion", "narrator", "brief", "critique"
- **Length override**: "short" (~5 min), "default" (~15 min), "long" (scales with article)
- **Voice override**: specific voice names like "Puck", "Kore", "alloy"

If only a URL is provided with no other options, use the auto-detected format and long length.
