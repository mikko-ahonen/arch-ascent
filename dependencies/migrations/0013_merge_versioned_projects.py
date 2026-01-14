"""
Data migration to merge duplicate projects that differ only by version.

The Checkmarx import was creating separate projects for each version of the same
component (e.g., pkg:maven/org.example/lib@1.0.0 and pkg:maven/org.example/lib@2.0.0).

This migration:
1. Finds all projects with versioned keys (containing @)
2. Groups them by their version-less key
3. For each group, keeps the project with the highest version (or first if no clear order)
4. Merges all dependencies and related records from duplicate projects to the kept project
5. Deletes the duplicate projects
"""

from django.db import migrations


def strip_version(purl: str) -> tuple[str, str | None]:
    """Strip the version from a purl."""
    if '@' in purl:
        base, version = purl.rsplit('@', 1)
        return base, version
    return purl, None


def merge_versioned_projects(apps, schema_editor):
    """Merge projects that differ only by version number."""
    Project = apps.get_model('dependencies', 'Project')
    Dependency = apps.get_model('dependencies', 'Dependency')
    LayerAssignment = apps.get_model('dependencies', 'LayerAssignment')
    LayerViolation = apps.get_model('dependencies', 'LayerViolation')
    NodeMetrics = apps.get_model('dependencies', 'NodeMetrics')

    # Vision app models (may not exist in all deployments)
    try:
        GroupMembership = apps.get_model('vision', 'GroupMembership')
    except LookupError:
        GroupMembership = None

    try:
        LayerNodePosition = apps.get_model('vision', 'LayerNodePosition')
    except LookupError:
        LayerNodePosition = None

    # Find all projects with versioned keys
    versioned_projects = Project.objects.filter(key__contains='@')

    # Group by version-less key
    groups = {}
    for project in versioned_projects:
        base_key, version = strip_version(project.key)
        if base_key not in groups:
            groups[base_key] = []
        groups[base_key].append((project, version))

    merged_count = 0
    deleted_count = 0

    for base_key, project_versions in groups.items():
        if len(project_versions) <= 1:
            # Only one version, just rename the key
            project, version = project_versions[0]
            project.key = base_key
            if version:
                project.description = f'v{version}'
            project.save()
            merged_count += 1
            continue

        # Multiple versions - need to merge
        # Sort by version (try semantic versioning, fall back to string sort)
        def version_key(pv):
            _, version = pv
            if not version:
                return (0, 0, 0, '')
            parts = version.split('.')
            try:
                # Try to parse as semantic version
                numeric_parts = []
                for p in parts[:3]:
                    # Strip non-numeric suffixes like "1.0.0-SNAPSHOT"
                    num = ''
                    for c in p:
                        if c.isdigit():
                            num += c
                        else:
                            break
                    numeric_parts.append(int(num) if num else 0)
                while len(numeric_parts) < 3:
                    numeric_parts.append(0)
                return tuple(numeric_parts) + (version,)
            except (ValueError, IndexError):
                return (0, 0, 0, version)

        # Sort descending to get highest version first
        project_versions.sort(key=version_key, reverse=True)

        # Keep the highest version project, update its key
        keeper, keeper_version = project_versions[0]
        keeper.key = base_key
        if keeper_version:
            keeper.description = f'v{keeper_version}'
        keeper.save()
        merged_count += 1

        # Merge all related records from other versions into keeper
        for project, version in project_versions[1:]:
            # --- Dependencies ---
            # Update dependencies where this project is the source
            for dep in Dependency.objects.filter(source=project):
                existing = Dependency.objects.filter(
                    source=keeper,
                    target=dep.target,
                    scope=dep.scope
                ).first()
                if not existing:
                    dep.source = keeper
                    dep.save()
                else:
                    dep.delete()

            # Update dependencies where this project is the target
            for dep in Dependency.objects.filter(target=project):
                existing = Dependency.objects.filter(
                    source=dep.source,
                    target=keeper,
                    scope=dep.scope
                ).first()
                if not existing:
                    dep.target = keeper
                    dep.save()
                else:
                    dep.delete()

            # --- LayerAssignment (OneToOne) ---
            # Keep keeper's assignment if it has one, otherwise take from duplicate
            try:
                dup_assignment = LayerAssignment.objects.get(project=project)
                if not LayerAssignment.objects.filter(project=keeper).exists():
                    dup_assignment.project = keeper
                    dup_assignment.save()
                else:
                    dup_assignment.delete()
            except LayerAssignment.DoesNotExist:
                pass

            # --- LayerViolation ---
            for violation in LayerViolation.objects.filter(source_project=project):
                violation.source_project = keeper
                violation.save()
            for violation in LayerViolation.objects.filter(target_project=project):
                violation.target_project = keeper
                violation.save()

            # --- NodeMetrics (OneToOne) ---
            try:
                dup_metrics = NodeMetrics.objects.get(project=project)
                if not NodeMetrics.objects.filter(project=keeper).exists():
                    dup_metrics.project = keeper
                    dup_metrics.save()
                else:
                    dup_metrics.delete()
            except NodeMetrics.DoesNotExist:
                pass

            # --- Vision GroupMembership ---
            if GroupMembership:
                for membership in GroupMembership.objects.filter(project=project):
                    existing = GroupMembership.objects.filter(
                        group=membership.group,
                        project=keeper
                    ).first()
                    if not existing:
                        membership.project = keeper
                        membership.save()
                    else:
                        membership.delete()

            # --- Vision LayerNodePosition ---
            if LayerNodePosition:
                for position in LayerNodePosition.objects.filter(project=project):
                    existing = LayerNodePosition.objects.filter(
                        layer=position.layer,
                        project=keeper
                    ).first()
                    if not existing:
                        position.project = keeper
                        position.save()
                    else:
                        position.delete()

            # Delete the duplicate project
            project.delete()
            deleted_count += 1

    if merged_count or deleted_count:
        print(f"\n  Merged {merged_count} projects, deleted {deleted_count} duplicates")


def reverse_merge(apps, schema_editor):
    """Reverse migration is not fully possible - just warn."""
    print("\n  Warning: Cannot fully reverse merge. Projects were consolidated.")


class Migration(migrations.Migration):

    dependencies = [
        ('dependencies', '0012_add_nodegroup_parent'),
    ]

    operations = [
        migrations.RunPython(merge_versioned_projects, reverse_merge),
    ]
