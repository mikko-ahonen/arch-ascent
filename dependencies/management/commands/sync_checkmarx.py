from django.core.management.base import BaseCommand
from dependencies.sync import (
    sync_checkmarx_projects,
    sync_checkmarx_dependencies,
    export_checkmarx_sboms,
    import_from_cached_sboms,
)
from dependencies.service import CheckmarxService, DEFAULT_SBOM_CACHE_DIR


class Command(BaseCommand):
    help = 'Synchronize projects and dependencies from Checkmarx One SCA'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url',
            type=str,
            help='Checkmarx One base URL (default: CHECKMARX_BASE_URL env var)',
        )
        parser.add_argument(
            '--iam-url',
            type=str,
            help='Checkmarx One IAM URL (default: derived from base URL or CHECKMARX_IAM_URL env var)',
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
            help='Directory for caching SBOM files (default: sbom_cache)',
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
        parser.add_argument(
            '--request-delay',
            type=float,
            help='Seconds to wait between API requests (default: 1.0 or CHECKMARX_REQUEST_DELAY env var)',
        )
        parser.add_argument(
            '--export-delay',
            type=float,
            help='Seconds to wait before SBOM export operations (default: 10.0 or CHECKMARX_EXPORT_DELAY env var)',
        )
        parser.add_argument(
            '--offline',
            action='store_true',
            help='Import from cached SBOM JSON files only, no HTTP requests',
        )
        parser.add_argument(
            '--internal-prefix',
            type=str,
            help='Purl prefix for internal packages (e.g., "pkg:maven/fi.company"). '
                 'Packages matching this prefix are marked as internal.',
        )

    def handle(self, *args, **options):
        base_url = options.get('base_url')
        iam_url = options.get('iam_url')
        tenant = options.get('tenant')
        client_id = options.get('client_id')
        client_secret = options.get('client_secret')
        cache_dir = options.get('cache_dir')
        projects_only = options.get('projects_only')
        export_only = options.get('export_only')
        dependencies_only = options.get('dependencies_only')
        skip_export = options.get('skip_export')
        request_delay = options.get('request_delay')
        export_delay = options.get('export_delay')
        offline = options.get('offline')
        internal_prefix = options.get('internal_prefix')

        # Offline mode: import from cached JSON files without any HTTP requests
        if offline:
            from pathlib import Path
            cache_path = Path(cache_dir or DEFAULT_SBOM_CACHE_DIR)
            if not cache_path.exists():
                self.stderr.write(self.style.ERROR(
                    f'Cache directory not found: {cache_path}'
                ))
                return

            self.stdout.write(f'Importing from cached SBOMs in {cache_path}...')
            if internal_prefix:
                self.stdout.write(f'  Internal prefix: {internal_prefix}')
            try:
                result = import_from_cached_sboms(
                    cache_path,
                    internal_prefix=internal_prefix,
                    on_progress=lambda p, d: (
                        self.stdout.write(f'  Processed: {p} projects, {d} dependencies', ending='\r'),
                        self.stdout.flush()
                    )
                )
                self.stdout.write('')  # newline after progress
                self.stdout.write(self.style.SUCCESS(
                    f'Offline import complete: {result["projects"]} projects, '
                    f'{result["dependencies"]} dependencies'
                ))
            except Exception as e:
                self.stdout.write('')
                self.stderr.write(self.style.ERROR(f'Failed: {e}'))
            return

        service = CheckmarxService(
            base_url=base_url,
            iam_url=iam_url,
            tenant=tenant,
            client_id=client_id,
            client_secret=client_secret,
            cache_dir=cache_dir,
            request_delay=request_delay,
            export_delay=export_delay,
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

        # Step 2: Export SBOMs sequentially (unless skipped)
        if not dependencies_only and not skip_export:
            delay_msg = f' (request delay: {request_delay}s)' if request_delay else ''
            self.stdout.write(f'Exporting SBOMs sequentially{delay_msg}...')
            self.stdout.write('  (Previously exported SBOMs will be skipped)')

            def on_progress(exported, skipped, processed):
                self.stdout.write(
                    f'  Processed: {processed} (exported: {exported}, cached: {skipped})',
                    ending='\r'
                )
                self.stdout.flush()

            try:
                with service:
                    result = export_checkmarx_sboms(service, on_progress=on_progress)
                self.stdout.write('')  # newline after progress
                self.stdout.write(self.style.SUCCESS(
                    f'SBOM export complete: {result["exported"]} exported, '
                    f'{result["skipped"]} cached'
                ))
            except Exception as e:
                self.stdout.write('')  # newline after progress
                self.stderr.write(self.style.ERROR(f'Failed: {e}'))
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
