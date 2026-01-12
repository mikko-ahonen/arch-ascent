---
name: close-issue
description: Close a bug or enhancement issue int he tracking system for this project
---

# Close a bug or enhancement

## Instructions

To close a bug or enhancement in the issue tracking system for this project, use 

```bash
.claude/skills/close-issue/scripts/close-issue 12 [--not-planned] --comment-file comment-file.md
```

Write a clear, concise and self-containing comment why the issue was
closed. 

By default, the issue is closed as completed.

If the issue is not planned to be fixed (won't fix, can't reproduce, 
stale), use optional --not-planned argument.

Refer to the issue identifier in commit message, prefixing with hash. 
For example "Fixed bug #12".

## Examples

```bash
.claude/skills/close-issue/scripts/close-issue --title "Fixed /reports returning 500" --body-file << EOF

### Problem

The reason was syntax error in the ReportListView. 

### Solution

Syntax error was fixed.

EOF
