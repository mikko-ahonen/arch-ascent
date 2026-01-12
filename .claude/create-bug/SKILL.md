---
name: create-bug
description: Create a bug in issue tracking system for this project
---

# Create a bug

## Instructions

To create a bug in issue tracking system for this project, use 

```bash
.claude/skills/create-bug/scripts/create-bug --title "bug title" --prio-high --body-file "bug-body.txt"
```

Write a clear, concise and self-containing description of the bug.
Include expected and observed behavior, as well as steps to produce.
if known. Use Markdown formatting sparingly for clarity. You can
optionally prioritize the issue with "--prio-low", "--prio-medium" 
or "--prio-high".

If issue creation is successful, URL is returned in the standard output,
that referes to the created ticket, such as this:

https://github.com/mikko-ahonen/usmtools/issues/12

The last path element tells the created issue number, in this instance
issue is 12. You can use the skill close-issue to close the issue 
by referencing with this number.

## Examples

```bash
.claude/skills/create-bug/scripts/create-bug --title "Page /reports returns 500" --prio-high --body-file << EOF

### Observed behavior

When running fetch_url.py /reports, HTTP error 500 is returned.

### Expected behavior

HTTP error 200 is expected.

### Steps to reproduce

&#96;&#96;&#96;bash
1.  load_url.py /reports
&#96;&#96;&#96;
EOF
