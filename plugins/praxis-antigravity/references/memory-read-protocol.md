# Memory read protocol (light tier and routed-down agents)

Prepend this to the brief of any agent running on the **light** tier, whether
it is declared light (`capability_tier: light`) or the delivery-lead routed it
down. Smaller models often skip their memory and act on the first theory that
fits; told explicitly to read first and test, they do markedly better
(Anthropic, "Components of agent memory", 2026). Larger tiers do not need it,
and rigid recording rules make them worse, so do not add it there.

> Before you answer or change anything:
> 1. Read the memory map in your session context (or run
>    `.project/local/bin/praxis-memory map`), then open the notes it points to
>    that bear on this task. Do not skip this step even if the task looks simple.
> 2. State your hypothesis, then check it against the code or a command output
>    before acting on it. If a note disagrees with the code, trust the code and
>    say which note is wrong.
> 3. Write a memory note only if a future session would act differently
>    because of it (`project-memory`, "When to write").
