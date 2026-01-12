import os
import logging
from dataclasses import dataclass
from typing import Iterator
import httpx

logger = logging.getLogger(__name__)


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
# Checkmarx SCA Cloud Service
# =============================================================================

# Default Checkmarx SCA cloud URLs
CHECKMARX_IAM_URL = 'https://iam.checkmarx.net'
CHECKMARX_API_URL = 'https://api-sca.checkmarx.net'


@dataclass
class CheckmarxProject:
    """Project data from Checkmarx SCA API."""
    id: str
    name: str
    created_on: str | None = None
    tags: dict | None = None


@dataclass
class CheckmarxDependency:
    """Dependency data from Checkmarx SCA."""
    source_project: str
    package_name: str
    version: str
    is_direct: bool = True


class CheckmarxService:
    """Checkmarx SCA Cloud API client for project and dependency synchronization."""

    def __init__(
        self,
        api_url: str | None = None,
        iam_url: str | None = None,
        tenant: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self.api_url = (api_url or os.environ.get('CHECKMARX_API_URL', CHECKMARX_API_URL)).rstrip('/')
        self.iam_url = (iam_url or os.environ.get('CHECKMARX_IAM_URL', CHECKMARX_IAM_URL)).rstrip('/')
        self.tenant = tenant or os.environ.get('CHECKMARX_TENANT', '')
        self.username = username or os.environ.get('CHECKMARX_USERNAME', '')
        self.password = password or os.environ.get('CHECKMARX_PASSWORD', '')
        self._client: httpx.Client | None = None
        self._access_token: str | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.api_url,
                timeout=30.0,
            )
            self._authenticate()
        return self._client

    def _authenticate(self):
        """Authenticate with Checkmarx IAM and obtain access token."""
        if not self.username or not self.password or not self.tenant:
            logger.warning("Checkmarx credentials not configured (need tenant, username, password)")
            return

        try:
            # Authenticate against IAM endpoint
            response = httpx.post(
                f'{self.iam_url}/identity/connect/token',
                data={
                    'username': self.username,
                    'password': self.password,
                    'acr_values': f'Tenant:{self.tenant}',
                    'grant_type': 'password',
                    'scope': 'sca_api',
                    'client_id': 'sca_resource_owner',
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data.get('access_token')
            logger.info("Checkmarx authentication successful")
        except httpx.HTTPStatusError as e:
            logger.error(f"Checkmarx authentication failed: {e}")

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Make authenticated GET request to Checkmarx SCA API."""
        headers = {}
        if self._access_token:
            headers['Authorization'] = f'Bearer {self._access_token}'

        response = self.client.get(f"/{endpoint}", params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_projects(self) -> Iterator[CheckmarxProject]:
        """Fetch all projects from Checkmarx SCA."""
        try:
            data = self._get('risk-management/projects')
            projects = data if isinstance(data, list) else data.get('items', [])
            for proj in projects:
                yield CheckmarxProject(
                    id=proj['id'],
                    name=proj['name'],
                    created_on=proj.get('createdOn'),
                    tags=proj.get('tags'),
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch Checkmarx projects: {e}")

    def get_project(self, project_id: str) -> CheckmarxProject | None:
        """Fetch a single project by ID."""
        try:
            data = self._get(f'risk-management/projects/{project_id}')
            if data:
                return CheckmarxProject(
                    id=data['id'],
                    name=data['name'],
                    created_on=data.get('createdOn'),
                    tags=data.get('tags'),
                )
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch project {project_id}: {e}")
        return None

    def get_dependencies(self, project_id: str) -> Iterator[CheckmarxDependency]:
        """Fetch dependencies for a project from latest scan."""
        try:
            # Get latest scan for the project
            scans = self._get('risk-management/scans', {'projectId': project_id})
            scan_list = scans if isinstance(scans, list) else scans.get('items', [])

            if not scan_list:
                return

            latest_scan = scan_list[0]
            scan_id = latest_scan['scanId']

            # Get packages from the scan
            packages = self._get(f'risk-management/scans/{scan_id}/packages')
            pkg_list = packages if isinstance(packages, list) else packages.get('items', [])

            for pkg in pkg_list:
                yield CheckmarxDependency(
                    source_project=project_id,
                    package_name=pkg.get('name', pkg.get('id', '')),
                    version=pkg.get('version', ''),
                    is_direct=pkg.get('isDirect', pkg.get('isDirectDependency', True)),
                )
        except httpx.HTTPStatusError as e:
            logger.debug(f"No dependencies for project {project_id}: {e}")
