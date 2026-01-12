#!/usr/bin/env python3
"""
Script to fetch page content, JavaScript errors and screen capture using playwright.

Usage:
    python check_page.py <url_or_path> [--restart] [--method METHOD] [--form-data DATA] [--json-data DATA]

Examples:
    # Using full URLs
    python check_page.py http://web:8000/vision/

    # Using relative paths (uses default server http://web:8000)
    python check_page.py /vision/
    python check_page.py /vision/test-editor/

    # Using relative path with custom server
    python check_page.py /vision/ --server-url http://web:8000

    # POST requests
    python check_page.py /api/endpoint/ --method POST --json-data '{"key": "value"}'
    python check_page.py /form/ --method POST --form-data 'field1=value1&field2=value2'

    # Restart server before testing
    python check_page.py /page/ --restart

Output files:
    - test-results/page-screenshot.png
    - test-results/page-content.html
    - test-results/browser-console.log
"""

import argparse
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 50)
    print(title)
    print("=" * 50)


def restart_server(server_url):
    """Restart the Django development server."""
    restart_url = f"{server_url}/restart"
    print(f"Restarting Django server at {restart_url}...")

    try:
        response = requests.get(restart_url, timeout=10)
        if response.status_code == 200:
            print("✓ Server restart initiated")
        else:
            print(f"⚠️  Server restart returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Could not restart server: {e}")
        print("Continuing anyway...")

    # Wait for server to come back up
    print("Waiting for server to be ready...")
    time.sleep(3)


def check_page(url, method="GET", form_data=None, json_data=None):
    """
    Load a page with Playwright and capture content, errors, and screenshot.

    Returns:
        tuple: (success: bool, js_errors: list, console_logs: list)
    """
    # Create test-results directory
    results_dir = Path('test-results')
    results_dir.mkdir(exist_ok=True)

    js_errors = []
    console_logs = []

    print(f"\n🌐 Loading page: {url}")
    print(f"   Method: {method}")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            ignore_https_errors=True
        )
        page = context.new_page()

        # Capture console messages
        def handle_console(msg):
            log_entry = f"[{msg.type}] {msg.text}"
            console_logs.append(log_entry)
            if msg.type == 'error':
                js_errors.append(msg.text)

        page.on('console', handle_console)

        # Capture page errors
        def handle_page_error(error):
            js_errors.append(str(error))

        page.on('pageerror', handle_page_error)

        try:
            # Navigate to page
            if method == "GET":
                response = page.goto(url, wait_until='networkidle', timeout=30000)
            else:
                # For POST, we need to use route interception or evaluate
                response = page.goto(url, wait_until='networkidle', timeout=30000)
                if form_data or json_data:
                    print(f"   Note: POST data handling requires form submission on page")

            # Wait a bit for any async JS to execute
            page.wait_for_timeout(1000)

            # Check response status
            if response:
                status = response.status
                print(f"   Status: {status}")
                if status >= 400:
                    js_errors.append(f"HTTP Error: {status}")

            # Take screenshot
            screenshot_path = results_dir / 'page-screenshot.png'
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"   📸 Screenshot saved: {screenshot_path}")

            # Save page content
            content_path = results_dir / 'page-content.html'
            content = page.content()
            content_path.write_text(content)
            print(f"   📄 Content saved: {content_path}")

            # Save console logs
            console_path = results_dir / 'browser-console.log'
            console_path.write_text('\n'.join(console_logs))
            print(f"   📋 Console log saved: {console_path}")

        except Exception as e:
            js_errors.append(f"Page load error: {str(e)}")
            print(f"   ❌ Error: {e}")

        finally:
            browser.close()

    return len(js_errors) == 0, js_errors, console_logs


def main():
    parser = argparse.ArgumentParser(
        description='Check for JavaScript errors on any page using Playwright',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('url', help='URL or path to test (e.g., http://web:8000/vision/ or /vision/)')
    parser.add_argument('--restart', action='store_true', help='Restart server before testing')
    parser.add_argument('--method', default='GET', help='HTTP method (GET or POST)')
    parser.add_argument('--form-data', help='Form data for POST requests (e.g., "field1=value1&field2=value2")')
    parser.add_argument('--json-data', help='JSON data for POST requests (e.g., \'{"key": "value"}\')')
    parser.add_argument('--server-url', default='http://web:8000', help='Server base URL for relative paths (default: http://web:8000)')

    args = parser.parse_args()

    # Handle relative URLs - prepend server URL if URL starts with /
    if args.url.startswith('/'):
        full_url = args.server_url.rstrip('/') + args.url
        print_header("Page Check")
        print(f"Path: {args.url}")
        print(f"Server: {args.server_url}")
        print(f"Full URL: {full_url}")
        args.url = full_url
    else:
        print_header("Page Check")
        print(f"URL: {args.url}")

    print(f"Method: {args.method}")

    if args.form_data:
        print(f"Form data: {args.form_data}")

    if args.json_data:
        print(f"JSON data: {args.json_data}")

    # Restart server if --restart is specified
    if args.restart:
        restart_server(args.server_url)
    else:
        print("\nSkipping server restart (use --restart to force restart)")

    # Run the page check
    success, js_errors, console_logs = check_page(
        args.url,
        args.method,
        args.form_data,
        args.json_data
    )

    # Print results
    print_header("Results")

    if js_errors:
        print(f"❌ Found {len(js_errors)} error(s):\n")
        for i, error in enumerate(js_errors, 1):
            print(f"  {i}. {error}")
        print()
        sys.exit(1)
    else:
        print("✅ No JavaScript errors detected!\n")
        sys.exit(0)


if __name__ == '__main__':
    main()
