"""
Management command to generate a large dataset of microservices for testing.
Creates multiple layers with intentionally conflicting groupings.
"""
import random
from django.core.management.base import BaseCommand
from dependencies.models import Project, Dependency
from vision.models import Vision, Layer, Group, GroupMembership


class Command(BaseCommand):
    help = 'Generate a large dataset of ~400 microservices with conflicting layers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=400,
            help='Target number of services to generate (default: 400)',
        )

    def handle(self, *args, **options):
        count = options['count']
        self.stdout.write(f'Generating ~{count} microservices with conflicting layers...')

        # Define GitLab-style repository groups (source code organization)
        gitlab_groups = {
            'platform/core': {
                'services': ['api-gateway', 'auth-service', 'config-server', 'discovery',
                            'logging', 'monitoring', 'tracing', 'secrets-manager'],
                'color': '#fc6d26',  # GitLab orange
            },
            'platform/data': {
                'services': ['postgres-service', 'redis-cache', 'elasticsearch', 'kafka',
                            'rabbitmq', 'mongodb', 's3-proxy', 'data-pipeline'],
                'color': '#6b4fbb',  # Purple
            },
            'services/payments': {
                'services': ['payment-api', 'payment-processor', 'payment-gateway',
                            'refund-service', 'billing-api', 'invoice-generator',
                            'subscription-manager', 'payment-webhook'],
                'color': '#2ecc71',  # Green
            },
            'services/users': {
                'services': ['user-api', 'profile-service', 'preferences-api',
                            'notification-preferences', 'user-search', 'avatar-service',
                            'user-activity', 'user-export'],
                'color': '#3498db',  # Blue
            },
            'services/orders': {
                'services': ['order-api', 'order-processor', 'fulfillment-service',
                            'shipping-calculator', 'tracking-service', 'returns-api',
                            'order-history', 'order-notifications'],
                'color': '#e74c3c',  # Red
            },
            'services/catalog': {
                'services': ['catalog-api', 'product-search', 'inventory-api',
                            'pricing-engine', 'promotions-api', 'category-service',
                            'product-import', 'media-service'],
                'color': '#f39c12',  # Yellow
            },
            'services/marketing': {
                'services': ['campaign-api', 'email-service', 'sms-gateway',
                            'push-notifications', 'ab-testing', 'analytics-collector',
                            'recommendation-engine', 'personalization-api'],
                'color': '#9b59b6',  # Purple
            },
            'services/support': {
                'services': ['ticket-api', 'chat-service', 'knowledge-base',
                            'feedback-collector', 'survey-service', 'escalation-api',
                            'agent-dashboard-api', 'support-analytics'],
                'color': '#1abc9c',  # Teal
            },
            'libs/shared': {
                'services': ['common-utils', 'validation-lib', 'logging-lib',
                            'metrics-lib', 'auth-client', 'http-client',
                            'event-publisher', 'cache-client'],
                'color': '#95a5a6',  # Gray
            },
            'mobile/backend': {
                'services': ['mobile-bff', 'mobile-auth', 'mobile-push',
                            'mobile-analytics', 'mobile-config', 'app-version-api',
                            'deep-link-service', 'mobile-gateway'],
                'color': '#e91e63',  # Pink
            },
        }

        # Define domain/bounded context organization (business domains)
        domain_groups = {
            'Payment Domain': {
                'services': ['payment-api', 'payment-processor', 'payment-gateway',
                            'refund-service', 'billing-api', 'invoice-generator',
                            'subscription-manager', 'payment-webhook',
                            # Cross-cutting: these also appear in other GitLab groups
                            'order-processor', 'mobile-bff'],
                'color': '#27ae60',
            },
            'Identity Domain': {
                'services': ['user-api', 'profile-service', 'auth-service',
                            'mobile-auth', 'auth-client', 'secrets-manager',
                            'preferences-api', 'notification-preferences'],
                'color': '#2980b9',
            },
            'Commerce Domain': {
                'services': ['order-api', 'order-processor', 'catalog-api',
                            'product-search', 'inventory-api', 'pricing-engine',
                            'promotions-api', 'shipping-calculator', 'fulfillment-service'],
                'color': '#c0392b',
            },
            'Engagement Domain': {
                'services': ['campaign-api', 'email-service', 'sms-gateway',
                            'push-notifications', 'mobile-push', 'notification-preferences',
                            'recommendation-engine', 'personalization-api', 'ab-testing'],
                'color': '#8e44ad',
            },
            'Support Domain': {
                'services': ['ticket-api', 'chat-service', 'knowledge-base',
                            'feedback-collector', 'survey-service', 'user-activity',
                            'support-analytics', 'escalation-api'],
                'color': '#16a085',
            },
            'Analytics Domain': {
                'services': ['analytics-collector', 'mobile-analytics', 'support-analytics',
                            'data-pipeline', 'elasticsearch', 'recommendation-engine',
                            'ab-testing', 'metrics-lib'],
                'color': '#d35400',
            },
            'Platform Domain': {
                'services': ['api-gateway', 'mobile-gateway', 'config-server',
                            'discovery', 'logging', 'monitoring', 'tracing',
                            'kafka', 'rabbitmq', 'redis-cache'],
                'color': '#7f8c8d',
            },
        }

        # Define team ownership organization
        team_groups = {
            'Team Alpha (Payments)': {
                'services': ['payment-api', 'payment-processor', 'payment-gateway',
                            'billing-api', 'subscription-manager'],
                'color': '#1e88e5',
            },
            'Team Beta (Identity)': {
                'services': ['user-api', 'auth-service', 'profile-service',
                            'mobile-auth', 'secrets-manager'],
                'color': '#43a047',
            },
            'Team Gamma (Orders)': {
                'services': ['order-api', 'order-processor', 'fulfillment-service',
                            'tracking-service', 'returns-api', 'shipping-calculator'],
                'color': '#e53935',
            },
            'Team Delta (Catalog)': {
                'services': ['catalog-api', 'product-search', 'inventory-api',
                            'pricing-engine', 'category-service', 'product-import'],
                'color': '#fb8c00',
            },
            'Team Epsilon (Marketing)': {
                'services': ['campaign-api', 'email-service', 'promotions-api',
                            'recommendation-engine', 'personalization-api'],
                'color': '#8e24aa',
            },
            'Team Zeta (Platform)': {
                'services': ['api-gateway', 'config-server', 'discovery',
                            'logging', 'monitoring', 'tracing', 'kafka', 'redis-cache',
                            'common-utils', 'logging-lib', 'metrics-lib'],
                'color': '#546e7a',
            },
            'Team Eta (Mobile)': {
                'services': ['mobile-bff', 'mobile-auth', 'mobile-push',
                            'mobile-analytics', 'mobile-config', 'mobile-gateway'],
                'color': '#ec407a',
            },
            'Team Theta (Support)': {
                'services': ['ticket-api', 'chat-service', 'knowledge-base',
                            'feedback-collector', 'agent-dashboard-api'],
                'color': '#26a69a',
            },
            'Team Shared': {
                'services': ['common-utils', 'validation-lib', 'auth-client',
                            'http-client', 'event-publisher', 'cache-client'],
                'color': '#78909c',
            },
        }

        # Generate all unique services from GitLab groups
        all_services = set()
        for group_data in gitlab_groups.values():
            all_services.update(group_data['services'])

        # Create projects
        projects = {}
        for service_name in sorted(all_services):
            project, created = Project.objects.get_or_create(
                key=service_name,
                defaults={
                    'name': service_name.replace('-', ' ').title(),
                    'description': f'{service_name} microservice'
                }
            )
            projects[service_name] = project
            if created:
                self.stdout.write(f'  Created: {service_name}')

        self.stdout.write(f'\nCreated {len(projects)} projects')

        # Generate dependencies
        self.stdout.write('\nGenerating dependencies...')
        dep_count = 0

        # API services depend on platform services
        platform_services = ['api-gateway', 'auth-service', 'config-server',
                           'redis-cache', 'kafka', 'logging', 'monitoring']

        for service_name, project in projects.items():
            # Most services depend on some platform services
            if service_name not in platform_services:
                for platform_svc in random.sample(platform_services, min(3, len(platform_services))):
                    if platform_svc in projects:
                        Dependency.objects.get_or_create(
                            source=project,
                            target=projects[platform_svc]
                        )
                        dep_count += 1

            # API services depend on their related services
            if '-api' in service_name:
                base_name = service_name.replace('-api', '')
                related = [s for s in projects.keys()
                          if base_name in s and s != service_name]
                for rel_svc in related[:3]:
                    Dependency.objects.get_or_create(
                        source=project,
                        target=projects[rel_svc]
                    )
                    dep_count += 1

        # Add cross-domain dependencies
        cross_deps = [
            ('order-processor', 'payment-api'),
            ('order-api', 'user-api'),
            ('payment-api', 'user-api'),
            ('fulfillment-service', 'inventory-api'),
            ('mobile-bff', 'user-api'),
            ('mobile-bff', 'order-api'),
            ('mobile-bff', 'catalog-api'),
            ('recommendation-engine', 'analytics-collector'),
            ('personalization-api', 'user-api'),
            ('campaign-api', 'user-api'),
        ]
        for source, target in cross_deps:
            if source in projects and target in projects:
                Dependency.objects.get_or_create(
                    source=projects[source],
                    target=projects[target]
                )
                dep_count += 1

        self.stdout.write(f'Created {dep_count} dependencies')

        # Create/update vision with conflicting layers
        self.stdout.write('\nCreating vision with conflicting layers...')

        vision, _ = Vision.objects.update_or_create(
            name="Enterprise Platform Vision",
            defaults={
                'description': 'Platform with multiple organizational perspectives (layers may conflict)',
                'status': 'draft'
            }
        )

        # Clear existing layers and groups for this vision
        vision.layers.all().delete()

        # Create Layer 1: GitLab Groups (source code organization)
        gitlab_layer = Layer.objects.create(
            key='gitlab-groups',
            name='GitLab Groups',
            vision=vision,
            layer_type='imported',
            color='#fc6d26',
            order=0
        )

        for group_path, group_data in gitlab_groups.items():
            group = Group.objects.create(
                key=group_path.replace('/', '-'),
                name=group_path,
                layer=gitlab_layer,
                color=group_data['color']
            )
            for service_name in group_data['services']:
                if service_name in projects:
                    GroupMembership.objects.create(
                        group=group,
                        project=projects[service_name],
                        membership_type='imported'
                    )

        # Create Layer 2: Domain/Bounded Contexts
        domain_layer = Layer.objects.create(
            key='domain-contexts',
            name='Domain Contexts',
            vision=vision,
            layer_type='bounded_context',
            color='#2ecc71',
            order=1
        )

        for domain_name, domain_data in domain_groups.items():
            group = Group.objects.create(
                key=domain_name.lower().replace(' ', '-'),
                name=domain_name,
                layer=domain_layer,
                color=domain_data['color']
            )
            for service_name in domain_data['services']:
                if service_name in projects:
                    GroupMembership.objects.create(
                        group=group,
                        project=projects[service_name],
                        membership_type='explicit'
                    )

        # Create Layer 3: Team Ownership
        team_layer = Layer.objects.create(
            key='team-ownership',
            name='Team Ownership',
            vision=vision,
            layer_type='team',
            color='#3498db',
            order=2
        )

        for team_name, team_data in team_groups.items():
            group = Group.objects.create(
                key=team_name.lower().replace(' ', '-').replace('(', '').replace(')', ''),
                name=team_name,
                layer=team_layer,
                color=team_data['color']
            )
            for service_name in team_data['services']:
                if service_name in projects:
                    GroupMembership.objects.create(
                        group=group,
                        project=projects[service_name],
                        membership_type='explicit'
                    )

        self.stdout.write(self.style.SUCCESS(f'''
Successfully generated dataset with conflicting layers!

  Projects: {len(projects)}
  Dependencies: {dep_count}

  Vision: {vision.name}
  Layers:
    1. GitLab Groups - Source code organization ({len(gitlab_groups)} groups)
    2. Domain Contexts - Business domain organization ({len(domain_groups)} groups)
    3. Team Ownership - Team responsibility ({len(team_groups)} groups)

  Note: The same service may appear in different groups across layers.
  For example:
    - 'payment-api' is in:
      * GitLab: services/payments
      * Domain: Payment Domain
      * Team: Team Alpha (Payments)

    - 'mobile-bff' is in:
      * GitLab: mobile/backend
      * Domain: Payment Domain (it handles payments!)
      * Team: Team Eta (Mobile)

View the vision at: /vision/{vision.id}/
Toggle layers to see different organizational perspectives.
'''))
