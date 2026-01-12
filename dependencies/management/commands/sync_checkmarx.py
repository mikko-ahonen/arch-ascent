from django.core.management.base import BaseCommand
from dependencies.sync import sync_checkmarx_projects, sync_checkmarx_dependencies
from dependencies.service import CheckmarxService


class Command(BaseCommand):
    help = 'Synchronize projects and dependencies from Checkmarx SCA Cloud'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Checkmarx tenant name (default: CHECKMARX_TENANT env var)',
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Checkmarx username (default: CHECKMARX_USERNAME env var)',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Checkmarx password (default: CHECKMARX_PASSWORD env var)',
        )
        parser.add_argument(
            '--api-url',
            type=str,
            help='Checkmarx SCA API URL (default: https://api-sca.checkmarx.net)',
        )
        parser.add_argument(
            '--iam-url',
            type=str,
            help='Checkmarx IAM URL (default: https://iam.checkmarx.net)',
        )
        parser.add_argument(
            '--projects-only',
            action='store_true',
            help='Only sync projects, skip dependencies',
        )
        parser.add_argument(
            '--dependencies-only',
            action='store_true',
            help='Only sync dependencies, skip projects',
        )

    def handle(self, *args, **options):
        tenant = options.get('tenant')
        username = options.get('username')
        password = options.get('password')
        api_url = options.get('api_url')
        iam_url = options.get('iam_url')
        projects_only = options.get('projects_only')
        dependencies_only = options.get('dependencies_only')

        service = CheckmarxService(
            api_url=api_url,
            iam_url=iam_url,
            tenant=tenant,
            username=username,
            password=password,
        )

        if not service.tenant:
            self.stderr.write(self.style.ERROR(
                'Checkmarx tenant not configured. Set CHECKMARX_TENANT env var or use --tenant'
            ))
            return

        if not dependencies_only:
            self.stdout.write('Syncing projects from Checkmarx SCA...')
            try:
                count = sync_checkmarx_projects(service)
                self.stdout.write(self.style.SUCCESS(f'Synced {count} projects'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed to sync projects: {e}'))
                return

        if not projects_only:
            self.stdout.write('Syncing dependencies from Checkmarx SCA...')
            try:
                count = sync_checkmarx_dependencies(service)
                self.stdout.write(self.style.SUCCESS(f'Synced {count} dependencies'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed to sync dependencies: {e}'))
                return

        self.stdout.write(self.style.SUCCESS('Checkmarx SCA sync complete'))
