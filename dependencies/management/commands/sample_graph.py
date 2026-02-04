import random
from django.core.management.base import BaseCommand
from dependencies.models import Component, Dependency, NodeGroup


class Command(BaseCommand):
    help = 'Create sample components and dependencies for graph testing'

    def handle(self, *args, **options):
        # Clear existing data
        Dependency.objects.all().delete()
        Component.objects.all().delete()
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

        # Generate 2000 components with domain:service naming convention
        for domain, services in domains.items():
            for service in services:
                for svc_type in random.sample(service_types, k=random.randint(1, 2)):
                    # Use domain:service-type naming convention for automatic grouping
                    key = f"{domain}:{service}-{svc_type}"
                    if key not in projects and len(projects) < 2000:
                        name = f"{service.replace('-', ' ').title()} {svc_type.title()}"
                        component = Component.objects.create(
                            name=name,
                            description=f"{name} for {domain} domain",
                            component_type='service',
                            group_id=domain,
                            artifact_id=f"{service}-{svc_type}",
                            group=groups[domain],
                        )
                        projects[key] = component
                        project_list.append((key, domain))

        # Fill remaining slots if needed
        extra_services = ['legacy', 'migration', 'batch', 'cron', 'admin', 'internal', 'external', 'public', 'private', 'shared']
        while len(projects) < 2000:
            svc = random.choice(extra_services)
            num = len(projects)
            key = f"misc:{svc}-{num}"
            name = f"{svc.title()} Service {num}"
            component = Component.objects.create(
                name=name,
                description=f"Additional service {num}",
                component_type='service',
                group_id='misc',
                artifact_id=f"{svc}-{num}",
                group=groups['misc'],
            )
            projects[key] = component
            project_list.append((key, 'misc'))

        self.stdout.write(f'Created {len(groups)} groups and {len(projects)} components')

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

        # Add many explicit cycles for testing cycle detection
        # Focus on longer cycles (3+ nodes), minimize 2-node cycles
        cycle_count = 0
        cycle_lengths = {3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0}

        # Helper to create a cycle of given length from a list of keys
        def create_cycle(keys, start_idx, length):
            nonlocal cycle_count
            if start_idx + length > len(keys):
                return False
            for j in range(length - 1):
                dependencies.add((keys[start_idx + j], keys[start_idx + j + 1]))
            dependencies.add((keys[start_idx + length - 1], keys[start_idx]))
            cycle_count += 1
            if length in cycle_lengths:
                cycle_lengths[length] += 1
            return True

        # Create varied-length cycles within each domain
        for domain, services in domains.items():
            domain_keys = [k for k, d in project_list if d == domain]
            random.shuffle(domain_keys)

            idx = 0
            # Create cycles of lengths 4, 5, 6 within domain
            for cycle_len in [4, 5, 6, 4, 5]:
                if idx + cycle_len <= len(domain_keys):
                    create_cycle(domain_keys, idx, cycle_len)
                    idx += cycle_len

        # Create long cross-domain cycles (7-8 nodes spanning multiple domains)
        all_domain_names = list(domains.keys())
        for i in range(20):  # Create 20 cross-domain long cycles
            # Pick 4 random domains
            selected_domains = random.sample(all_domain_names, min(4, len(all_domain_names)))
            cycle_nodes = []
            for dom in selected_domains:
                dom_keys = [k for k, d in project_list if d == dom]
                if dom_keys:
                    cycle_nodes.extend(random.sample(dom_keys, min(2, len(dom_keys))))

            if len(cycle_nodes) >= 5:
                # Create cycle through these nodes
                for j in range(len(cycle_nodes) - 1):
                    dependencies.add((cycle_nodes[j], cycle_nodes[j + 1]))
                dependencies.add((cycle_nodes[-1], cycle_nodes[0]))
                cycle_count += 1
                cycle_lengths[min(len(cycle_nodes), 8)] = cycle_lengths.get(min(len(cycle_nodes), 8), 0) + 1

        # Create medium cycles (3-4 nodes) across related domains
        domain_pairs = [
            ('commerce', 'fulfillment'),
            ('commerce', 'customer'),
            ('analytics', 'integration'),
            ('content', 'communication'),
            ('platform', 'core'),
            ('mobile', 'content'),
        ]
        for dom1, dom2 in domain_pairs:
            keys1 = [k for k, d in project_list if d == dom1]
            keys2 = [k for k, d in project_list if d == dom2]
            for i in range(min(10, len(keys1), len(keys2))):
                # 4-node cycle: dom1 -> dom1 -> dom2 -> dom2 -> dom1
                if i + 1 < len(keys1) and i + 1 < len(keys2):
                    dependencies.add((keys1[i], keys1[i + 1]))
                    dependencies.add((keys1[i + 1], keys2[i]))
                    dependencies.add((keys2[i], keys2[i + 1]))
                    dependencies.add((keys2[i + 1], keys1[i]))
                    cycle_count += 1
                    cycle_lengths[4] += 1

        # Create longer cycles in misc (5-8 nodes)
        misc_keys = [k for k, d in project_list if d == 'misc']
        random.shuffle(misc_keys)
        idx = 0
        for cycle_len in [5, 6, 7, 8, 5, 6, 7, 8, 5, 6, 7, 8] * 10:
            if idx + cycle_len <= len(misc_keys):
                create_cycle(misc_keys, idx, cycle_len)
                idx += cycle_len

        # Only add a few 2-node cycles (direct bidirectional) for comparison
        for domain in ['core', 'platform']:
            domain_keys = [k for k, d in project_list if d == domain]
            if len(domain_keys) >= 2:
                dependencies.add((domain_keys[0], domain_keys[1]))
                dependencies.add((domain_keys[1], domain_keys[0]))
                cycle_count += 1
                cycle_lengths[2] = cycle_lengths.get(2, 0) + 1

        self.stdout.write(f'Added {cycle_count} explicit cycles')
        self.stdout.write(f'Cycle lengths: {dict(sorted(cycle_lengths.items()))}')

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
