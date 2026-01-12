from django.core.management.base import BaseCommand
from dependencies.sync import sync_projects, sync_dependencies
from dependencies.service import SonarQubeService


class Command(BaseCommand):
    help = 'Synchronize projects and dependencies from SonarQube'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='SonarQube URL (default: SONARQUBE_URL env var)',
        )
        parser.add_argument(
            '--token',
            type=str,
            help='SonarQube API token (default: SONARQUBE_TOKEN env var)',
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
        url = options.get('url')
        token = options.get('token')
        projects_only = options.get('projects_only')
        dependencies_only = options.get('dependencies_only')

        service = SonarQubeService(base_url=url, token=token)

        if not service.base_url:
            self.stderr.write(self.style.ERROR(
                'SonarQube URL not configured. Set SONARQUBE_URL env var or use --url'
            ))
            return

        if not dependencies_only:
            self.stdout.write('Syncing projects from SonarQube...')
            try:
                count = sync_projects(service)
                self.stdout.write(self.style.SUCCESS(f'Synced {count} projects'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed to sync projects: {e}'))
                return

        if not projects_only:
            self.stdout.write('Syncing dependencies from SonarQube...')
            try:
                count = sync_dependencies(service)
                self.stdout.write(self.style.SUCCESS(f'Synced {count} dependencies'))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed to sync dependencies: {e}'))
                return

        self.stdout.write(self.style.SUCCESS('SonarQube sync complete'))
