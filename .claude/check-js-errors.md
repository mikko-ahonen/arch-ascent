# JavaScript Error Checker Skill

This skill checks for JavaScript errors in the Django diagram page.

## What it does

1. Reloads the Django development server by touching models.py
2. Checks source code for problematic `${getTimestamp()}` patterns in console calls
3. Runs Playwright E2E tests to capture JavaScript errors
4. Reports detailed error information with line numbers and stack traces
5. Returns exit code 0 for success, 1 for errors

## Usage

When the user asks you to check for JavaScript errors or test the diagram page, use this skill:

1. Ask the user for a version number (for cache busting) or generate one based on timestamp
2. Run the check script: `/src/check_js_errors.sh <version>`
3. Report the results to the user

## Example prompts that should trigger this skill

- "Check for JavaScript errors"
- "Test the diagram page for errors"
- "Run the JS error checker"
- "Are there any JavaScript errors?"
- "Validate the diagram page"

## Instructions

When this skill is invoked:

1. Generate a version number (can be timestamp or sequential number)
2. Execute: `bash /src/check_js_errors.sh <version>`
3. Wait for the script to complete (may take 20-30 seconds)
4. Report the results:
   - If exit code 0: Report success and confirm no errors
   - If exit code 1: Report the error count and show details from the output
5. If errors are found, suggest next steps:
   - Check the line number in the source file
   - Look at the error type (SyntaxError vs ReferenceError vs TypeError)
   - Suggest fixes based on the error pattern

## Important notes

- Always reload the Django server before testing (the script does this automatically)
- Use version numbers for cache busting
- The script checks both source code patterns AND runtime errors
- Syntax errors appear as "Unexpected token" errors
- Runtime errors appear with specific error types (ReferenceError, TypeError, etc.)

## Script location

`/src/check_js_errors.sh`

## Key files to check when debugging

- `/src/components/modeling/diagram.html` - Main diagram component with JavaScript
- `/src/e2e/diagram.spec.js` - Playwright test that captures errors
- `/src/modeling/models.py` - Touch this to reload Django server
