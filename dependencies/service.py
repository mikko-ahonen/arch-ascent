import os
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import httpx

logger = logging.getLogger(__name__)

# Default cache directory for SBOM files
DEFAULT_SBOM_CACHE_DIR = os.environ.get('SBOM_CACHE_DIR', 'sbom_cache')


# =============================================================================
# SonarQube Service
# =============================================================================


@dataclass
class SonarProject:
    """Project data from SonarQube API."""
    key: str
    name: str
    description: str = ''
    qualifier: str = 'TRK'
    visibility: str = 'public'
    last_analysis: str | None = None


@dataclass
class SonarDependency:
    """Dependency data from SonarQube API."""
    source_key: str
    target_key: str
    scope: str = 'compile'
    weight: int = 1


class SonarQubeService:
    """Minimal SonarQube API client for project synchronization."""

    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or os.environ.get('SONARQUBE_URL', '')).rstrip('/')
        self.token = token or os.environ.get('SONARQUBE_TOKEN', '')
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                auth=(self.token, '') if self.token else None,
                timeout=30.0,
            )
        return self._client

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make GET request to SonarQube API."""
        response = self.client.get(f"/api/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()

    def get_projects(self, page_size: int = 100) -> Iterator[SonarProject]:
        """Fetch all projects with pagination."""
        page = 1
        while True:
            data = self._get('projects/search', {
                'ps': page_size,
                'p': page,
            })

            components = data.get('components', [])
            if not components:
                break

            for comp in components:
                yield SonarProject(
                    key=comp['key'],
                    name=comp['name'],
                    description=comp.get('description', ''),
                    qualifier=comp.get('qualifier', 'TRK'),
                    visibility=comp.get('visibility', 'public'),
                    last_analysis=comp.get('lastAnalysisDate'),
                )

            paging = data.get('paging', {})
            total = paging.get('total', 0)
            if page * page_size >= total:
                break
            page += 1

    def get_project(self, key: str) -> SonarProject | None:
        """Fetch a single project by key."""
        try:
            data = self._get('projects/search', {'projects': key})
            components = data.get('components', [])
            if components:
                comp = components[0]
                return SonarProject(
                    key=comp['key'],
                    name=comp['name'],
                    description=comp.get('description', ''),
                    qualifier=comp.get('qualifier', 'TRK'),
                    visibility=comp.get('visibility', 'public'),
                    last_analysis=comp.get('lastAnalysisDate'),
                )
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch project {key}: {e}")
        return None

    def get_dependencies(self, project_key: str) -> Iterator[SonarDependency]:
        """Fetch dependencies for a project."""
        try:
            data = self._get('measures/component', {
                'component': project_key,
                'metricKeys': 'dependencies',
            })
            # Parse dependency metrics if available
            component = data.get('component', {})
            for measure in component.get('measures', []):
                if measure.get('metric') == 'dependencies':
                    # Dependencies typically come as a formatted string or JSON
                    # This parsing may need adjustment based on SonarQube version
                    deps_value = measure.get('value', '')
                    for dep in self._parse_dependencies(project_key, deps_value):
                        yield dep
        except httpx.HTTPStatusError as e:
            logger.debug(f"No dependencies for {project_key}: {e}")

    def _parse_dependencies(self, source_key: str, deps_value: str) -> Iterator[SonarDependency]:
        """Parse dependency value from SonarQube measures."""
        if not deps_value:
            return
        # Format varies by SonarQube version/plugin
        # Common format: "group:artifact:version" per line
        for line in deps_value.strip().split('\n'):
            line = line.strip()
            if line and ':' in line:
                yield SonarDependency(
                    source_key=source_key,
                    target_key=line,
                )


# =============================================================================
# Checkmarx One SCA Service
# =============================================================================


@dataclass
class CheckmarxProject:
    """Project data from Checkmarx One API."""
    id: str
    name: str
    created_on: str | None = None
    tags: dict | None = None


@dataclass
class CheckmarxDependency:
    """Dependency data from Checkmarx One SCA."""
    source_project: str
    package_name: str
    version: str
    is_direct: bool = True


class CheckmarxService:
    """Checkmarx One SCA API client using OAuth client credentials.

    Required configuration (via constructor or environment variables):
    - base_url: Checkmarx One base URL (e.g., https://ast.checkmarx.net)
    - tenant: Tenant identifier
    - client_id: OAuth client ID
    - client_secret: OAuth client secret

    Optional:
    - cache_dir: Directory for caching SBOM files (default: .sbom_cache)
    """

    def __init__(
        self,
        base_url: str | None = None,
        iam_url: str | None = None,
        tenant: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        cache_dir: str | None = None,
        request_delay: float | None = None,
    ):
        self.base_url = (base_url or os.environ.get('CHECKMARX_BASE_URL', '')).rstrip('/')
        self.tenant = tenant or os.environ.get('CHECKMARX_TENANT', '')
        self.client_id = client_id or os.environ.get('CHECKMARX_CLIENT_ID', '')
        self.client_secret = client_secret or os.environ.get('CHECKMARX_CLIENT_SECRET', '')
        self.cache_dir = Path(cache_dir or DEFAULT_SBOM_CACHE_DIR)
        self._client: httpx.Client | None = None
        self._access_token: str | None = None

        # Throttle delay between API requests (seconds)
        if request_delay is not None:
            self.request_delay = request_delay
        else:
            env_delay = os.environ.get('CHECKMARX_REQUEST_DELAY', '')
            self.request_delay = float(env_delay) if env_delay else 1.0

        # Use explicit IAM URL or derive from base URL
        if iam_url:
            self._iam_url = iam_url.rstrip('/')
        elif os.environ.get('CHECKMARX_IAM_URL'):
            self._iam_url = os.environ.get('CHECKMARX_IAM_URL', '').rstrip('/')
        elif self.base_url:
            # Derive: https://ast.checkmarx.net -> https://iam.checkmarx.net
            self._iam_url = self.base_url.replace('.ast.', '.iam.').replace('://ast.', '://iam.')
        else:
            self._iam_url = ''

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=30.0,
            )
            self._authenticate()
        return self._client

    def _authenticate(self):
        """Authenticate using OAuth client credentials flow."""
        if not self.client_id or not self.client_secret or not self.tenant:
            raise ValueError("Checkmarx credentials not configured (need base_url, tenant, client_id, client_secret)")

        try:
            # OAuth token endpoint using client credentials grant
            token_url = f'{self._iam_url}/auth/realms/{self.tenant}/protocol/openid-connect/token'
            response = httpx.post(
                token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data.get('access_token')
            logger.info("Checkmarx One authentication successful")
        except httpx.HTTPStatusError as e:
            logger.error(f"Checkmarx One authentication failed: {e}")
            raise

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _throttle(self):
        """Wait before making a request to avoid overloading the server."""
        if self.request_delay > 0:
            logger.info(f"Throttling: waiting {self.request_delay}s before next request")
            time.sleep(self.request_delay)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict | list:
        """Make authenticated request to Checkmarx One API."""
        # Ensure we're authenticated
        if not self._access_token:
            self._authenticate()

        # Wait before making request
        self._throttle()

        headers = {
            'Authorization': f'Bearer {self._access_token}',
        }

        endpoint = endpoint.lstrip('/')
        url = f"{self.base_url}/{endpoint}"

        logger.info(f"Request: {method} {url}")

        response = httpx.request(
            method,
            url,
            params=params,
            json=json_data,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()

        return response.json()

    def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Make authenticated GET request."""
        return self._request('GET', endpoint, params=params)

    def _post(self, endpoint: str, json_data: dict | None = None) -> dict | list:
        """Make authenticated POST request."""
        return self._request('POST', endpoint, json_data=json_data)

    def get_projects(self) -> Iterator[CheckmarxProject]:
        """Fetch all projects from Checkmarx One with pagination."""
        offset = 0
        limit = 100
        while True:
            data = self._get('api/projects', {'offset': offset, 'limit': limit})
            projects = data.get('projects', [])
            total_count = data.get('totalCount', 0)

            for proj in projects:
                yield CheckmarxProject(
                    id=proj['id'],
                    name=proj['name'],
                    created_on=proj.get('createdAt'),
                    tags=proj.get('tags'),
                )

            offset += limit
            if offset >= total_count or not projects:
                break

    def get_project(self, project_id: str) -> CheckmarxProject | None:
        """Fetch a single project by ID."""
        try:
            data = self._get(f'api/projects/{project_id}')
            if data:
                return CheckmarxProject(
                    id=data['id'],
                    name=data['name'],
                    created_on=data.get('createdAt'),
                    tags=data.get('tags'),
                )
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch project {project_id}: {e}")
        return None

    def get_scans(self, project_id: str) -> list[dict]:
        """Fetch scans for a project."""
        data = self._get('api/scans', {'project-id': project_id})
        return data if isinstance(data, list) else data.get('scans', [])

    def _get_cache_path(self, scan_id: str) -> Path:
        """Get the cache file path for a scan's SBOM."""
        # Sanitize scan_id for safe filenames (alphanumeric, hyphen, underscore only)
        safe_id = ''.join(c if c.isalnum() or c in '-_' else '_' for c in scan_id)
        return self.cache_dir / f"{safe_id}.json"

    def _ensure_cache_dir(self):
        """Ensure the cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cached_sbom(self, scan_id: str) -> dict | None:
        """Get cached SBOM for a scan if it exists.

        Args:
            scan_id: The scan ID

        Returns:
            Parsed SBOM dict if cached, None otherwise
        """
        cache_path = self._get_cache_path(scan_id)
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read cached SBOM for {scan_id}: {e}")
        return None

    def is_sbom_cached(self, scan_id: str) -> bool:
        """Check if SBOM is already cached for a scan."""
        return self._get_cache_path(scan_id).exists()

    def list_cached_scans(self) -> list[str]:
        """List all scan IDs that have cached SBOMs."""
        if not self.cache_dir.exists():
            return []
        return [p.stem for p in self.cache_dir.glob('*.json')]

    def export_sbom(
        self,
        scan_id: str,
        output_path: str | None = None,
        hide_dev_dependencies: bool = False,
        poll_interval: float = 2.0,
        max_wait: float = 300.0,
        use_cache: bool = True,
    ) -> str:
        """Export SBOM in CycloneDX JSON format for a scan.

        Args:
            scan_id: The scan ID to export SBOM for
            output_path: Local file path to save the SBOM JSON (default: cache directory)
            hide_dev_dependencies: Whether to exclude dev/test dependencies
            poll_interval: Seconds between status checks
            max_wait: Maximum seconds to wait for export completion
            use_cache: If True, return cached SBOM if available (default: True)

        Returns:
            Path to the saved SBOM file

        Raises:
            TimeoutError: If export doesn't complete within max_wait
            httpx.HTTPStatusError: On API errors
        """
        import time

        self._ensure_cache_dir()

        # Use cache path if no output path specified
        if output_path is None:
            output_path = str(self._get_cache_path(scan_id))

        # Check cache first
        if use_cache and Path(output_path).exists():
            logger.info(f"Using cached SBOM for scan {scan_id}")
            return output_path

        # Request SBOM export via Export Service API
        export_response = self._post('api/sca/export/requests', {
            'ScanId': scan_id,
            'FileFormat': 'CycloneDxJson',
            'ExportParameters': {
                'hideDevAndTestDependencies': hide_dev_dependencies,
            },
        })
        export_id = export_response['exportId']
        logger.info(f"SBOM export requested, exportId: {export_id}")

        # Poll for completion
        elapsed = 0.0
        while elapsed < max_wait:
            status_response = self._get('api/sca/export/requests', {'exportId': export_id})
            status = status_response.get('exportStatus')

            if status == 'Completed':
                file_url = status_response.get('fileUrl')
                if not file_url:
                    raise ValueError("Export completed but no fileUrl provided")

                # Download the SBOM file
                self._throttle()
                logger.info(f"Downloading SBOM from {file_url}")
                download_response = httpx.get(file_url, timeout=60.0)
                download_response.raise_for_status()

                # Save to local file (cache)
                with open(output_path, 'wb') as f:
                    f.write(download_response.content)

                logger.info(f"Cached SBOM to file: {output_path}")
                return output_path

            elif status == 'Failed':
                raise RuntimeError(f"SBOM export failed for scan {scan_id}")

            time.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"SBOM export timed out after {max_wait}s for scan {scan_id}")

    def get_dependencies_from_sbom(self, scan_id: str, project_id: str) -> Iterator[CheckmarxDependency]:
        """Extract dependencies from a cached or exported SBOM.

        Args:
            scan_id: The scan ID
            project_id: The project ID (used for source reference)

        Yields:
            CheckmarxDependency objects
        """
        # Try to get from cache first
        sbom = self.get_cached_sbom(scan_id)

        if sbom is None:
            # Export and cache the SBOM
            self.export_sbom(scan_id)
            sbom = self.get_cached_sbom(scan_id)

        if sbom is None:
            logger.warning(f"Could not get SBOM for scan {scan_id}")
            return

        # Extract components from CycloneDX format
        for component in sbom.get('components', []):
            yield CheckmarxDependency(
                source_project=project_id,
                package_name=component.get('name', ''),
                version=component.get('version', ''),
                is_direct=component.get('scope') != 'optional',
            )

    def get_dependencies(self, project_id: str) -> Iterator[CheckmarxDependency]:
        """Fetch dependencies for a project from latest scan.

        This parses the SBOM export to extract dependency information.
        For full SBOM data, use export_sbom() directly.
        """
        try:
            # Get latest scan for the project
            scans = self.get_scans(project_id)
            if not scans:
                return

            latest_scan = scans[0]
            scan_id = latest_scan.get('id') or latest_scan.get('scanId')

            yield from self.get_dependencies_from_sbom(scan_id, project_id)

        except Exception as e:
            logger.debug(f"No dependencies for project {project_id}: {e}")
