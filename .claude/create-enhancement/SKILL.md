---
name: create-enhancement
description: Create an enhancement in issue tracking system for this project
---

# Create an enhancement

## Instructions

To create an enhancement in issue tracking system for this project, use 

```bash
.claude/skills/create-enhancement/scripts/create-enhancement --title "enhancement title" --prio-medium --body-file "enhancement-body.txt"
```

Write a clear, concise and self-containing description of the enhancement.
If there are many closely related enhancements in single app, bundle them into 
single enhancement. If you have a proposal, you may suggest it. Include consequnces, if known. Use Markdown formatting 
sparingly for clarity.  You can
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
.claude/skills/create-enhancement/scripts/create-enhancement --title "reports does implement authorization checks" --prio-high --body-file << EOF

### Description

reports app does not implement authorization checks.

### Proposal

Implement authorization checks similarly as in other apps.

### Consequences

Unauthorized users may access data from other tenants.

EOF
