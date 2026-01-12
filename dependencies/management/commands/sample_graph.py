import random
from django.core.management.base import BaseCommand
from dependencies.models import Project, Dependency, NodeGroup


class Command(BaseCommand):
    help = 'Create sample projects and dependencies for graph testing'

    def handle(self, *args, **options):
        # Clear existing data
        Dependency.objects.all().delete()
        Project.objects.all().delete()
        NodeGroup.objects.all().delete()

        # Define service domains
        domains = {
            'core': ['api-gateway', 'auth', 'user', 'config', 'discovery', 'logging', 'metrics', 'tracing'],
            'commerce': ['product', 'catalog', 'pricing', 'inventory', 'cart', 'checkout', 'order', 'payment', 'invoice', 'refund'],
            'fulfillment': ['warehouse', 'shipping', 'delivery', 'tracking', 'returns', 'logistics'],
            'customer': ['crm', 'loyalty', 'support', 'feedback', 'survey', 'preferences'],
            'communication': ['email', 'sms', 'push', 'notification', 'template', 'scheduler'],
            'content': ['cms', 'media', 'search', 'recommendation', 'personalization', 'ab-testing'],
            'analytics': ['events', 'reporting', 'dashboard', 'export', 'etl', 'warehouse-analytics'],
            'integration': ['erp', 'crm-sync', 'payment-gateway', 'shipping-provider', 'tax', 'fraud'],
            'platform': ['file-storage', 'cache', 'queue', 'database', 'secrets', 'feature-flags'],
            'mobile': ['ios-api', 'android-api', 'mobile-gateway', 'deep-linking', 'app-config'],
        }

        # Service types
        service_types = ['service', 'api', 'worker', 'lib', 'connector']

        projects = {}
        project_list = []
        groups = {}

        # Create groups for each domain
        for domain in list(domains.keys()) + ['misc']:
            group = NodeGroup.objects.create(
                key=domain,
                name=domain.title(),
            )
            groups[domain] = group

        # Generate 150 projects with domain:service naming convention
        for domain, services in domains.items():
            for service in services:
                for svc_type in random.sample(service_types, k=random.randint(1, 2)):
                    # Use domain:service-type naming convention for automatic grouping
                    key = f"{domain}:{service}-{svc_type}"
                    if key not in projects and len(projects) < 150:
                        name = f"{service.replace('-', ' ').title()} {svc_type.title()}"
                        project = Project.objects.create(
                            key=key,
                            name=name,
                            description=f"{name} for {domain} domain",
                            group=groups[domain],
                        )
                        projects[key] = project
                        project_list.append((key, domain))

        # Fill remaining slots if needed
        extra_services = ['legacy', 'migration', 'batch', 'cron', 'admin', 'internal', 'external', 'public', 'private', 'shared']
        while len(projects) < 150:
            svc = random.choice(extra_services)
            num = len(projects)
            key = f"misc:{svc}-{num}"
            name = f"{svc.title()} Service {num}"
            project = Project.objects.create(
                key=key,
                name=name,
                description=f"Additional service {num}",
                group=groups['misc'],
            )
            projects[key] = project
            project_list.append((key, 'misc'))

        self.stdout.write(f'Created {len(groups)} groups and {len(projects)} projects')

        # Core services that many depend on
        core_services = [k for k, d in project_list if d == 'core' or 'lib' in k or 'connector' in k]
        platform_services = [k for k, d in project_list if d == 'platform']

        # Generate dependencies
        dependencies = set()

        for key, domain in project_list:
            # Each service depends on 1-3 core services
            for core in random.sample(core_services, k=min(random.randint(1, 3), len(core_services))):
                if core != key:
                    dependencies.add((key, core))

            # Each service depends on 0-2 platform services
            if platform_services:
                for platform in random.sample(platform_services, k=min(random.randint(0, 2), len(platform_services))):
                    if platform != key:
                        dependencies.add((key, platform))

            # Services in same domain depend on each other
            same_domain = [k for k, d in project_list if d == domain and k != key]
            if same_domain:
                for dep in random.sample(same_domain, k=min(random.randint(0, 3), len(same_domain))):
                    dependencies.add((key, dep))

        # Add some cross-domain dependencies
        commerce_keys = [k for k, d in project_list if d == 'commerce']
        fulfillment_keys = [k for k, d in project_list if d == 'fulfillment']
        communication_keys = [k for k, d in project_list if d == 'communication']

        for commerce in commerce_keys[:5]:
            for fulfillment in random.sample(fulfillment_keys, k=min(2, len(fulfillment_keys))):
                dependencies.add((commerce, fulfillment))
            for comm in random.sample(communication_keys, k=min(2, len(communication_keys))):
                dependencies.add((commerce, comm))

        # Create dependency records
        dep_count = 0
        for source_key, target_key in dependencies:
            if source_key in projects and target_key in projects:
                Dependency.objects.create(
                    source=projects[source_key],
                    target=projects[target_key],
                )
                dep_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Created {len(groups)} groups, {len(projects)} projects and {dep_count} dependencies'
        ))
