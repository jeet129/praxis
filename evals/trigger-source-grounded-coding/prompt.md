---
max_turns: 6
runs: 3
tags: [trigger]
allowed_tools: [Read, Glob, Grep, Skill]
---

Add retry handling using the queue client library we already depend on. Make sure you use its real API rather than guessing.
