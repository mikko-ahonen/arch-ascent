---
name: check-page
description: Request page capturing page content, JavaScript errors
and taking a screen capture
---

# Request page capturing page content, JavaScript errors and taking screen capture

With this script, a page can requested, optionally with form data,
It saves the page content, JavaScript errors and a screen capture
be taken using Playwright to a file.

It can also optionally restart the server before request.

## Instructions

Use the project root to run the skill.

```bash
python .claude/check-page/scripts/check_page.py <url_or_path> [--restart] [--method METHOD] [--form-data DATA] [--json-data DATA] [--server-url URL]
```

## Examples

### Using full URLs
```bash
python .claude/check-page/scripts/check_page.py http://web:8000/vision/
```

### Using relative paths (uses default server http://web:8000)

```bash
python .claude/check-page/scripts/check_page.py /vision/
python .claude/check-page/scripts/check_page.py /vision/test-editor/
```

### Using relative path with custom server

```bash
python .claude/check-page/scripts/check_page.py /vision/ --server-url http://web:8000
```

### POST requests
```bash
python .claude/check-page/scripts/check_page.py /api/endpoint/ --method POST --json-data '{"key": "value"}'
python .claude/check-page/scripts/check_page.py /form/ --method POST --form-data 'field1=value1&field2=value2'
```

### Restart server before testing
```bash
python .claude/check-page/scripts/check_page.py /page/ --restart
```

## Output files

- test-results/page-screenshot.png
- test-results/page-content.html
- test-results/browser-console.log
