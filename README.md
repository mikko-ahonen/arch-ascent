# Dependencies

A web application for visualizing project dependency graphs from SonarQube and Checkmarx. Built with Django, HTMX, and Cytoscape.js.

## Features

- **Graph Visualization**: Interactive dependency graph with drag-and-drop nodes
- **Automatic Grouping**: Projects are automatically grouped based on naming conventions (e.g., `domain:project-name`)
- **Manual Grouping**: Select nodes and group them manually
- **Auto-Clustering**: DBSCAN-based clustering to automatically group nearby nodes
- **Transitive Dependencies**: Toggle visibility of transitive (redundant) edges
- **Filtering**: Filter projects by name with wildcard support (`core:*`, `*:auth:*`)
- **Layout Persistence**: Save node positions and groups to the database
- **SonarQube Integration**: Import projects and dependencies from SonarQube
- **Checkmarx Integration**: Import projects and SCA dependencies from Checkmarx

## Requirements

- Python 3.11+
- Docker & Docker Compose (optional)

## Quick Start

### Using Docker

```bash
docker-compose up
```

The application will be available at http://localhost:8050

### Manual Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create sample data (optional)
python manage.py sample_graph

# Start server
python manage.py runserver
```

## Data Synchronization

### SonarQube

Set environment variables:

```bash
export SONARQUBE_URL=https://sonarqube.example.com
export SONARQUBE_TOKEN=your-api-token
```

Sync projects and dependencies:

```bash
# Sync everything
python manage.py sync_sonarqube

# Sync only projects
python manage.py sync_sonarqube --projects-only

# Sync only dependencies
python manage.py sync_sonarqube --dependencies-only

# Use custom URL/token
python manage.py sync_sonarqube --url https://sonar.example.com --token xxx
```

### Checkmarx SCA (Cloud)

Set environment variables:

```bash
export CHECKMARX_TENANT=your-tenant-name
export CHECKMARX_USERNAME=your-username
export CHECKMARX_PASSWORD=your-password
```

Sync projects and dependencies:

```bash
# Sync everything
python manage.py sync_checkmarx

# Sync only projects
python manage.py sync_checkmarx --projects-only

# Sync only dependencies
python manage.py sync_checkmarx --dependencies-only

# Use custom credentials
python manage.py sync_checkmarx --tenant mytenant --username user --password pass

# Use custom API endpoints (for different regions)
python manage.py sync_checkmarx --api-url https://api-sca.eu.checkmarx.net --iam-url https://eu.iam.checkmarx.net
```

## Usage

### Graph Controls

| Button | Description |
|--------|-------------|
| Labels | Toggle project name labels |
| Transitive | Toggle transitive dependency edges |
| Group | Group selected nodes |
| Ungroup | Ungroup selected group |
| Cluster | Auto-cluster nodes by position |
| Fit | Fit graph to screen |
| Relayout | Re-run force-directed layout |
| Save | Save node positions and groups |
| Refresh | Reload graph from database |

### Scoping View

The Scoping view provides tools for analyzing and selecting projects for further work.

#### Centrality Highlighting

Use the **Highlight...** dropdown in the graph view to identify important nodes based on network metrics:

| Metric | Description |
|--------|-------------|
| By Degree | Highlights nodes with many direct connections (hubs) |
| By Betweenness | Highlights nodes that act as bridges between other nodes |
| By Closeness | Highlights nodes with short average distance to all others |
| By Eigenvector | Highlights nodes connected to other influential nodes |

The threshold slider (percentile) controls how many nodes are highlighted. Highlights persist when switching between graph and list views. Use **Select highlighted** to check all highlighted rows for bulk actions.

#### Filter Panel

- **By Analysis Status**: Filter by project status (Active, Stale, Dormant, etc.)
- **By Connectivity**: Filter by graph connectivity (Main cluster, Disconnected, Unused)
- **By Group**: Filter by project group (collapsed by default, click to expand)
- **By Tag**: Filter by project tags
- **By Name Pattern**: Filter using wildcards (e.g., `service-*`, `*-api`)

### Filtering

Enter filter terms in the search box (comma-separated):

- `foo` - matches projects containing "foo"
- `core:*` - matches all projects starting with "core:"
- `*:auth:*` - matches projects with "auth" in the middle
- `*-service` - matches projects ending with "-service"

Filtered view shows matching projects plus all their direct dependencies.

### Mouse Controls

- **Click**: Select node
- **Drag**: Move node
- **Scroll**: Zoom in/out
- **Click + Drag background**: Pan

## Project Structure

```
src/
├── config/              # Django settings
├── main/                # Main app (views, URLs)
├── dependencies/        # Dependencies app
│   ├── components/      # Django components
│   │   └── graph/       # Graph visualization component
│   ├── management/      # Management commands
│   │   └── commands/
│   │       ├── sample_graph.py
│   │       ├── sync_sonarqube.py
│   │       └── sync_checkmarx.py
│   ├── models.py        # Project, Dependency, NodeGroup models
│   ├── service.py       # SonarQube & Checkmarx API clients
│   └── sync.py          # Sync logic
├── components/          # Shared components
├── templates/           # Base templates
└── static/              # Static files
```

## Tech Stack

- **Backend**: Django 5.x, django-components
- **Frontend**: Bootstrap 5.3, HTMX, Cytoscape.js
- **Database**: SQLite (default)

## License

MIT
