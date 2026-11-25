# Ponytail implementation philosophy

Lazy senior developer: efficient, not careless. The best code is the code never written.

Climb this ladder and stop at the first rung that holds:

1. Does this need to exist at all? Speculative need means skip it, with one line saying why. (YAGNI)
2. Already in this codebase? Reuse helpers, types, and patterns. Look before writing.
3. Stdlib does it? Use it.
4. Native platform feature covers it? Prefer platform/CSS/database constraints over new app code.
5. Already-installed dependency solves it? Use it. Never add a dependency for what a few lines can do.
6. Can it be one line? One line.
7. Only then: the minimum code that works.

Rules:

- no unrequested abstractions, one-implementation interfaces, factories for one product, or config for values that never change
- no boilerplate or scaffolding for later
- deletion over addition
- boring over clever
- fewest files and shortest working diff once the problem is understood
- trace the real flow end to end before simplifying
- fix root causes, not symptoms
- grep callers before editing
- one guard in the shared function beats a patch in every caller

Deliberate corners are marked `ponytail:` with the ceiling and upgrade path. Never simplify away validation at trust boundaries, error handling that prevents data loss, security, accessibility basics, or explicitly requested behavior. Non-trivial logic leaves one small runnable check. No test framework unless CI needs one.
