"""
Management command to analyze dependency graph and generate refactoring proposals.

Usage:
    # Run full analysis
    python manage.py analyze_refactoring

    # Dry run (don't save proposals)
    python manage.py analyze_refactoring --dry-run

    # Only analyze SCCs
    python manage.py analyze_refactoring --scc-only

    # Set minimum SCC size
    python manage.py analyze_refactoring --min-scc-size 3

    # Use specific model
    python manage.py analyze_refactoring --model claude-sonnet-4-20250514
"""

from django.core.management.base import BaseCommand
from dependencies.refactoring_pipeline import RefactoringPipeline
from dependencies.llm_service import RefactoringAnalyzer


class Command(BaseCommand):
    help = 'Analyze dependency graph and generate refactoring proposals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run analysis without saving proposals to database',
        )
        parser.add_argument(
            '--scc-only',
            action='store_true',
            help='Only analyze strongly connected components (cycles)',
        )
        parser.add_argument(
            '--coupling-only',
            action='store_true',
            help='Only analyze high-coupling services',
        )
        parser.add_argument(
            '--boundaries-only',
            action='store_true',
            help='Only analyze community boundaries',
        )
        parser.add_argument(
            '--min-scc-size',
            type=int,
            default=2,
            help='Minimum SCC size to analyze (default: 2)',
        )
        parser.add_argument(
            '--coupling-threshold',
            type=float,
            default=90,
            help='Percentile threshold for high coupling (default: 90)',
        )
        parser.add_argument(
            '--model',
            type=str,
            default='claude-sonnet-4-20250514',
            help='LLM model to use (default: claude-sonnet-4-20250514)',
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='Anthropic API key (default: ANTHROPIC_API_KEY env var)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        scc_only = options.get('scc_only', False)
        coupling_only = options.get('coupling_only', False)
        boundaries_only = options.get('boundaries_only', False)
        min_scc_size = options.get('min_scc_size', 2)
        coupling_threshold = options.get('coupling_threshold', 90)
        model = options.get('model', 'claude-sonnet-4-20250514')
        api_key = options.get('api_key')

        # Determine which analyses to run
        if scc_only or coupling_only or boundaries_only:
            analyze_sccs = scc_only
            analyze_coupling = coupling_only
            analyze_boundaries = boundaries_only
        else:
            analyze_sccs = True
            analyze_coupling = True
            analyze_boundaries = True

        # Create services
        llm_service = RefactoringAnalyzer(api_key=api_key, model=model)
        pipeline = RefactoringPipeline(llm_service=llm_service, dry_run=dry_run)

        if not llm_service.is_available:
            self.stdout.write(self.style.WARNING(
                'LLM not available (missing API key). Will generate placeholder proposals.'
            ))

        self.stdout.write(f'Starting refactoring analysis...')
        self.stdout.write(f'  - Analyze SCCs: {analyze_sccs}')
        self.stdout.write(f'  - Analyze coupling: {analyze_coupling}')
        self.stdout.write(f'  - Analyze boundaries: {analyze_boundaries}')
        self.stdout.write(f'  - Min SCC size: {min_scc_size}')
        self.stdout.write(f'  - Coupling threshold: {coupling_threshold}%')
        self.stdout.write(f'  - Dry run: {dry_run}')

        try:
            run = pipeline.run_analysis(
                min_scc_size=min_scc_size,
                coupling_threshold=coupling_threshold,
                analyze_sccs=analyze_sccs,
                analyze_coupling=analyze_coupling,
                analyze_boundaries=analyze_boundaries,
            )

            self.stdout.write(self.style.SUCCESS(
                f'\nAnalysis complete!'
            ))
            self.stdout.write(f'  - Total projects: {run.total_projects}')
            self.stdout.write(f'  - SCCs found: {run.total_sccs}')
            self.stdout.write(f'  - Clusters found: {run.total_clusters}')
            self.stdout.write(f'  - Proposals generated: {run.proposals_generated}')

            if dry_run:
                self.stdout.write(self.style.WARNING(
                    '\nDry run mode - proposals were not saved to database.'
                ))

            # Show summary of proposals
            if run.proposals_generated > 0:
                self.stdout.write('\nProposal summary:')
                from dependencies.models import RefactoringProposal
                for proposal in RefactoringProposal.objects.filter(analysis_run=run):
                    self.stdout.write(
                        f'  [{proposal.proposal_id}] {proposal.get_proposal_type_display()}: '
                        f'{proposal.summary[:60]}...'
                    )

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Analysis failed: {e}'))
            raise
