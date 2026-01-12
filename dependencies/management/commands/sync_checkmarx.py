from django.core.management.base import BaseCommand
from dependencies.sync import (
    sync_checkmarx_projects,
    sync_checkmarx_dependencies,
    export_checkmarx_sboms,
)
from dependencies.service import CheckmarxService


class Command(BaseCommand):
    help = 'Synchronize projects and dependencies from Checkmarx One SCA'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url',
            type=str,
            help='Checkmarx One base URL (default: CHECKMARX_BASE_URL env var)',
        )
        parser.add_argument(
            '--tenant',
            type=str,
            help='Checkmarx tenant identifier (default: CHECKMARX_TENANT env var)',
        )
        parser.add_argument(
            '--client-id',
            type=str,
            help='OAuth client ID (default: CHECKMARX_CLIENT_ID env var)',
        )
        parser.add_argument(
            '--client-secret',
            type=str,
            help='OAuth client secret (default: CHECKMARX_CLIENT_SECRET env var)',
        )
        parser.add_argument(
            '--cache-dir',
            type=str,
            help='Directory for caching SBOM files (default: .sbom_cache)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of SBOMs to export per batch (default: 10)',
        )
        parser.add_argument(
            '--batch-delay',
            type=float,
            default=10.0,
            help='Seconds to wait between batches (default: 10.0)',
        )
        parser.add_argument(
            '--projects-only',
            action='store_true',
            help='Only sync projects, skip SBOM export and dependencies',
        )
        parser.add_argument(
            '--export-only',
            action='store_true',
            help='Only export SBOMs (resumes from cache), skip project sync and dependency import',
        )
        parser.add_argument(
            '--dependencies-only',
            action='store_true',
            help='Only sync dependencies from cached SBOMs, skip project sync and SBOM export',
        )
        parser.add_argument(
            '--skip-export',
            action='store_true',
            help='Skip SBOM export, only use cached SBOMs for dependencies',
        )

    def handle(self, *args, **options):
        base_url = options.get('base_url')
        tenant = options.get('tenant')
        client_id = options.get('client_id')
        client_secret = options.get('client_secret')
        cache_dir = options.get('cache_dir')
        batch_size = options.get('batch_size')
        batch_delay = options.get('batch_delay')
        projects_only = options.get('projects_only')
        export_only = options.get('export_only')
        dependencies_only = options.get('dependencies_only')
        skip_export = options.get('skip_export')

        service = CheckmarxService(
            base_url=base_url,
            tenant=tenant,
            client_id=client_id,
            client_secret=client_secret,
            cache_dir=cache_dir,
        )

        if not service.base_url:
            self.stderr.write(self.style.ERROR(
                'Checkmarx base URL not configured. Set CHECKMARX_BASE_URL env var or use --base-url'
            ))
            return

        if not service.tenant:
            self.stderr.write(self.style.ERROR(
                'Checkmarx tenant not configured. Set CHECKMARX_TENANT env var or use --tenant'
            ))
            return

        # Step 1: Sync projects (unless skipped)
        if not dependencies_only and not export_only:
            self.stdout.write('Syncing projects from Checkmarx One...')
            try:
                count = sync_checkmarx_projects(service)
                self.stdout.write(self.style.SUCCESS(f'Synced {count} projects'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed to sync projects: {e}'))
                return

        if projects_only:
            self.stdout.write(self.style.SUCCESS('Checkmarx One project sync complete'))
            return

        # Step 2: Export SBOMs in batches (unless skipped)
        if not dependencies_only and not skip_export:
            self.stdout.write(f'Exporting SBOMs (batch size: {batch_size}, delay: {batch_delay}s)...')
            self.stdout.write('  (Previously exported SBOMs will be skipped)')

            def on_progress(exported, skipped, failed, total):
                self.stdout.write(
                    f'  Progress: {exported + skipped + failed}/{total} '
                    f'(exported: {exported}, cached: {skipped}, failed: {failed})',
                    ending='\r'
                )
                self.stdout.flush()

            try:
                with service:
                    result = export_checkmarx_sboms(
                        service,
                        batch_size=batch_size,
                        batch_delay=batch_delay,
                        on_progress=on_progress,
                    )
                self.stdout.write('')  # newline after progress
                self.stdout.write(self.style.SUCCESS(
                    f'SBOM export complete: {result["exported"]} exported, '
                    f'{result["skipped"]} cached, {result["failed"]} failed'
                ))
                if result['errors']:
                    for err in result['errors'][:5]:  # Show first 5 errors
                        self.stderr.write(f'  Error: {err["project"]}: {err["error"]}')
                    if len(result['errors']) > 5:
                        self.stderr.write(f'  ... and {len(result["errors"]) - 5} more errors')
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed to export SBOMs: {e}'))
                return

        if export_only:
            self.stdout.write(self.style.SUCCESS('Checkmarx One SBOM export complete'))
            return

        # Step 3: Sync dependencies from cached SBOMs
        self.stdout.write('Syncing dependencies from cached SBOMs...')
        try:
            use_cached_only = skip_export or dependencies_only
            count = sync_checkmarx_dependencies(service, use_cached_only=use_cached_only)
            self.stdout.write(self.style.SUCCESS(f'Synced {count} dependencies'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to sync dependencies: {e}'))
            return

        self.stdout.write(self.style.SUCCESS('Checkmarx One sync complete'))
