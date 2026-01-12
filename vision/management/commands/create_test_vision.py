"""
Management command to create test vision data for development.
"""
from django.core.management.base import BaseCommand
from dependencies.models import Project, Dependency
from vision.models import Vision, Layer, Group, GroupMembership, Reference, Statement


class Command(BaseCommand):
    help = 'Create test vision data for development'

    def handle(self, *args, **options):
        self.stdout.write('Creating test vision data...')

        # Create projects if they don't exist
        projects_data = [
            # Payment Domain
            ('payment-api', 'Payment API', 'Main payment API service'),
            ('payment-processor', 'Payment Processor', 'Handles payment processing'),
            ('payment-gateway', 'Payment Gateway', 'External payment gateway integration'),
            ('billing-service', 'Billing Service', 'Billing and invoicing'),

            # User Domain
            ('user-api', 'User API', 'User management API'),
            ('auth-service', 'Auth Service', 'Authentication and authorization'),
            ('profile-service', 'Profile Service', 'User profile management'),

            # Order Domain
            ('order-api', 'Order API', 'Order management API'),
            ('order-processor', 'Order Processor', 'Order processing service'),
            ('inventory-service', 'Inventory Service', 'Inventory management'),

            # Infrastructure
            ('api-gateway', 'API Gateway', 'Main API gateway'),
            ('message-queue', 'Message Queue', 'Message broker service'),
            ('cache-service', 'Cache Service', 'Caching layer'),
        ]

        projects = {}
        for key, name, desc in projects_data:
            project, created = Project.objects.get_or_create(
                key=key,
                defaults={'name': name, 'description': desc}
            )
            projects[key] = project
            if created:
                self.stdout.write(f'  Created project: {name}')

        # Add tags to projects
        projects['payment-api'].tags.add('payment', 'api', 'domain')
        projects['payment-processor'].tags.add('payment', 'internal')
        projects['payment-gateway'].tags.add('payment', 'external')
        projects['billing-service'].tags.add('payment', 'billing')
        projects['user-api'].tags.add('user', 'api', 'domain')
        projects['auth-service'].tags.add('user', 'security')
        projects['profile-service'].tags.add('user', 'internal')
        projects['order-api'].tags.add('order', 'api', 'domain')
        projects['order-processor'].tags.add('order', 'internal')
        projects['inventory-service'].tags.add('order', 'inventory')
        projects['api-gateway'].tags.add('infrastructure', 'gateway')
        projects['message-queue'].tags.add('infrastructure', 'messaging')
        projects['cache-service'].tags.add('infrastructure', 'cache')

        # Create dependencies
        dependencies_data = [
            # API Gateway routes to domain APIs
            ('api-gateway', 'payment-api'),
            ('api-gateway', 'user-api'),
            ('api-gateway', 'order-api'),

            # Payment domain
            ('payment-api', 'payment-processor'),
            ('payment-processor', 'payment-gateway'),
            ('payment-api', 'billing-service'),
            ('billing-service', 'payment-processor'),

            # User domain
            ('user-api', 'auth-service'),
            ('user-api', 'profile-service'),
            ('auth-service', 'cache-service'),

            # Order domain
            ('order-api', 'order-processor'),
            ('order-processor', 'inventory-service'),
            ('order-api', 'message-queue'),
            ('order-processor', 'message-queue'),

            # Cross-domain dependencies
            ('order-api', 'payment-api'),
            ('order-api', 'user-api'),
            ('payment-api', 'user-api'),
        ]

        for source_key, target_key in dependencies_data:
            source = projects.get(source_key)
            target = projects.get(target_key)
            if source and target:
                Dependency.objects.get_or_create(source=source, target=target)

        # Create Vision
        vision, created = Vision.objects.get_or_create(
            name="E-Commerce Platform Vision",
            defaults={
                'description': 'Architectural vision for the e-commerce microservices platform',
                'status': 'draft'
            }
        )
        if created:
            self.stdout.write(f'  Created vision: {vision.name}')

        # Create Layers
        layers_data = [
            ('presentation', 'Presentation Layer', 'freeform', '#3498db', 0),
            ('domain', 'Domain Layer', 'bounded_context', '#2ecc71', 1),
            ('infrastructure', 'Infrastructure Layer', 'freeform', '#9b59b6', 2),
        ]

        layers = {}
        for key, name, layer_type, color, order in layers_data:
            layer, created = Layer.objects.get_or_create(
                key=key,
                vision=vision,
                defaults={
                    'name': name,
                    'layer_type': layer_type,
                    'color': color,
                    'order': order
                }
            )
            layers[key] = layer
            if created:
                self.stdout.write(f'  Created layer: {name}')

        # Create Groups within layers
        groups_data = [
            # Presentation layer
            ('presentation', 'gateway', 'API Gateway', '#5dade2'),

            # Domain layer - bounded contexts
            ('domain', 'payment-context', 'Payment Context', '#58d68d'),
            ('domain', 'user-context', 'User Context', '#f4d03f'),
            ('domain', 'order-context', 'Order Context', '#eb984e'),

            # Infrastructure layer
            ('infrastructure', 'shared-infra', 'Shared Infrastructure', '#af7ac5'),
        ]

        groups = {}
        for layer_key, group_key, name, color in groups_data:
            layer = layers.get(layer_key)
            if layer:
                group, created = Group.objects.get_or_create(
                    key=group_key,
                    layer=layer,
                    defaults={
                        'name': name,
                        'color': color
                    }
                )
                groups[group_key] = group
                if created:
                    self.stdout.write(f'  Created group: {name}')

        # Add projects to groups
        memberships_data = [
            ('gateway', 'api-gateway'),

            ('payment-context', 'payment-api'),
            ('payment-context', 'payment-processor'),
            ('payment-context', 'payment-gateway'),
            ('payment-context', 'billing-service'),

            ('user-context', 'user-api'),
            ('user-context', 'auth-service'),
            ('user-context', 'profile-service'),

            ('order-context', 'order-api'),
            ('order-context', 'order-processor'),
            ('order-context', 'inventory-service'),

            ('shared-infra', 'message-queue'),
            ('shared-infra', 'cache-service'),
        ]

        for group_key, project_key in memberships_data:
            group = groups.get(group_key)
            project = projects.get(project_key)
            if group and project:
                GroupMembership.objects.get_or_create(
                    group=group,
                    project=project,
                    defaults={'membership_type': 'explicit'}
                )

        # Create References
        references_data = [
            ('PaymentServices', 'tag_expression', {'or': ['payment']}, 'All payment-related services'),
            ('DomainAPIs', 'tag_expression', {'and': ['api', 'domain']}, 'All domain API services'),
            ('InfrastructureServices', 'tag_expression', {'or': ['infrastructure']}, 'All infrastructure services'),
        ]

        for name, def_type, expr, desc in references_data:
            Reference.objects.get_or_create(
                name=name,
                vision=vision,
                defaults={
                    'definition_type': def_type,
                    'tag_expression': expr,
                    'description': desc
                }
            )

        # Create Statements
        statements_data = [
            ('existence', 'There must be a payment gateway service', {'reference': 'PaymentServices'}),
            ('containment', 'All domain APIs must be behind the API Gateway', None),
            ('exclusion', 'Infrastructure services must not directly depend on domain services', None),
            ('cardinality', 'There should be exactly one API Gateway', {'reference': 'gateway', 'operator': '==', 'value': 1}),
        ]

        for stmt_type, natural, formal in statements_data:
            Statement.objects.get_or_create(
                vision=vision,
                natural_language=natural,
                defaults={
                    'statement_type': stmt_type,
                    'formal_expression': formal,
                    'status': 'semi_formal' if formal else 'informal'
                }
            )

        self.stdout.write(self.style.SUCCESS('Successfully created test vision data!'))
        self.stdout.write(f'  Vision: {vision.name}')
        self.stdout.write(f'  Layers: {vision.layers.count()}')
        self.stdout.write(f'  References: {vision.references.count()}')
        self.stdout.write(f'  Statements: {vision.statements.count()}')
        self.stdout.write(f'\nView the vision at: /vision/{vision.id}/')
