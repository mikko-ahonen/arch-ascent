#!/usr/bin/env python
"""Debug script for Checkmarx One API authentication and connectivity."""

import os
import sys
import json
import base64
import requests


def decode_jwt(token):
    """Decode JWT payload without verification."""
    try:
        payload = token.split('.')[1]
        payload += '=' * (4 - len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception as e:
        return {'error': str(e)}


def main():
    base = os.environ.get('CHECKMARX_BASE_URL', '').rstrip('/')
    iam = os.environ.get('CHECKMARX_IAM_URL', '').rstrip('/')
    tenant = os.environ.get('CHECKMARX_TENANT', '')
    client_id = os.environ.get('CHECKMARX_CLIENT_ID', '')
    client_secret = os.environ.get('CHECKMARX_CLIENT_SECRET', '')

    # Derive IAM URL if not set
    if not iam and base:
        iam = base.replace('.ast.', '.iam.').replace('://ast.', '://iam.')

    print('=' * 60)
    print('CONFIGURATION')
    print('=' * 60)
    print(f'Base URL:      {base}')
    print(f'IAM URL:       {iam}')
    print(f'Tenant:        {tenant}')
    print(f'Client ID:     {client_id}')
    print(f'Client Secret: {client_secret[:8]}...' if client_secret else 'Client Secret: (not set)')
    print()

    if not all([base, iam, tenant, client_id, client_secret]):
        print('ERROR: Missing required environment variables')
        print('Required: CHECKMARX_BASE_URL, CHECKMARX_TENANT, CHECKMARX_CLIENT_ID, CHECKMARX_CLIENT_SECRET')
        sys.exit(1)

    # Step 1: Get token
    print('=' * 60)
    print('STEP 1: Authentication')
    print('=' * 60)
    token_url = f'{iam}/auth/realms/{tenant}/protocol/openid-connect/token'
    print(f'Token URL: {token_url}')

    r = requests.post(token_url, data={
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
    })
    print(f'Status: {r.status_code}')

    if r.status_code != 200:
        print(f'FAILED: {r.text}')
        sys.exit(1)

    token = r.json().get('access_token')
    print(f'Token: {token[:50]}...')
    print()

    # Decode token
    print('=' * 60)
    print('TOKEN CLAIMS')
    print('=' * 60)
    claims = decode_jwt(token)
    print(json.dumps(claims, indent=2))
    print()

    headers = {'Authorization': f'Bearer {token}'}

    # Step 2: Test endpoints
    endpoints = [
        ('Userinfo (IAM)', f'{iam}/auth/realms/{tenant}/protocol/openid-connect/userinfo', {}),
        ('Whoami', f'{base}/api/whoami', {}),
        ('Projects', f'{base}/api/projects', {'offset': 0, 'limit': 10}),
        ('Scans', f'{base}/api/scans', {'offset': 0, 'limit': 10}),
    ]

    print('=' * 60)
    print('STEP 2: API Endpoints')
    print('=' * 60)

    for name, url, params in endpoints:
        print(f'\n--- {name} ---')
        print(f'URL: {url}')
        if params:
            print(f'Params: {params}')

        try:
            r = requests.get(url, headers=headers, params=params if params else None)
            print(f'Status: {r.status_code}')

            if r.status_code == 200:
                try:
                    data = r.json()
                    if isinstance(data, dict):
                        print(f'Keys: {list(data.keys())}')
                        if 'totalCount' in data:
                            print(f'Total count: {data["totalCount"]}')
                    print(f'Response: {r.text[:300]}...' if len(r.text) > 300 else f'Response: {r.text}')
                except:
                    print(f'Response: {r.text[:300]}')
            else:
                print(f'Response: {r.text[:500]}')
        except Exception as e:
            print(f'ERROR: {e}')

    print()
    print('=' * 60)
    print('DONE')
    print('=' * 60)


if __name__ == '__main__':
    main()
