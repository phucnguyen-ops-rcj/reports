# Code Conventions

- **Comments for complex logic**: Add short comments for non-obvious or complex business logic when they help explain the "why" or intended result, especially around pandas transforms, aggregations, conditional filtering, and ratio calculations. Do not add comments mechanically or restate obvious code. Example:
  ```python
  # Calculate P&L per unit volume (scaled to percentage)
  return calculate_ratio_column(summary_df, "npnl_r+un", "volume_$", "npnl/volume_%", scale=100)
  ```
  This helps future readers understand the intent without adding noise to straightforward code.

- **Git commits**: Write a clear, concise commit message (imperative mood, under 70 characters in the subject line). Let `git` handle attribution naturally.

# Coding Behaviour

- **Ask before assuming**: surface ambiguity and tradeoffs before implementing; if multiple interpretations exist, present them.
- **Minimum viable change**: no features, abstractions, or error handling beyond what was asked. If it could be 50 lines, don't write 200.
- **Surgical edits**: touch only what the task requires. Don't improve adjacent code, fix formatting, or remove pre-existing dead code. Remove imports/variables that *your* changes made unused.
- **Verify before closing**: every task should have a clear done-state (tests pass, script runs, error gone). State it upfront for multi-step work.
