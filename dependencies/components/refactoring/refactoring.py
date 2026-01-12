"""
Django component for displaying and managing refactoring proposals.
"""

import json
from django_components import Component, register
from django.http import HttpRequest, HttpResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from dependencies.models import RefactoringProposal, AnalysisRun


@register("refactoring_backlog")
class RefactoringBacklog(Component):
    template_name = "refactoring/refactoring.html"

    def get_context_data(
        self,
        proposal_type: str = None,
        impact: str = None,
        risk: str = None,
        status: str = None,
    ):
        proposals = RefactoringProposal.objects.all()

        # Apply filters
        if proposal_type:
            proposals = proposals.filter(proposal_type=proposal_type)
        if impact:
            proposals = proposals.filter(impact=impact)
        if risk:
            proposals = proposals.filter(risk=risk)
        if status:
            proposals = proposals.filter(status=status)

        # Get proposal types with counts
        proposal_types_with_counts = []
        for ptype, label in RefactoringProposal.PROPOSAL_TYPES:
            count = RefactoringProposal.objects.filter(proposal_type=ptype).count()
            proposal_types_with_counts.append((ptype, label, count))

        # Get latest analysis run
        latest_run = AnalysisRun.objects.first()

        return {
            "proposals": proposals[:50],  # Limit to 50
            "total_count": RefactoringProposal.objects.count(),
            "latest_run": latest_run,
            "proposal_types": proposal_types_with_counts,
            "impact_choices": RefactoringProposal.IMPACT_CHOICES,
            "risk_choices": RefactoringProposal.RISK_CHOICES,
            "status_choices": RefactoringProposal.STATUS_CHOICES,
            "current_filters": {
                "proposal_type": proposal_type,
                "impact": impact,
                "risk": risk,
                "status": status,
            },
        }

    @staticmethod
    def htmx_list(request: HttpRequest):
        """Return filtered proposal list."""
        proposal_type = request.GET.get('type')
        impact = request.GET.get('impact')
        risk = request.GET.get('risk')
        status = request.GET.get('status')

        return RefactoringBacklog.render_to_response(
            kwargs={
                "proposal_type": proposal_type,
                "impact": impact,
                "risk": risk,
                "status": status,
            },
            request=request,
        )

    @staticmethod
    def htmx_detail(request: HttpRequest, proposal_id: str):
        """Return detailed view of a proposal."""
        try:
            proposal = RefactoringProposal.objects.get(proposal_id=proposal_id)
            return HttpResponse(RefactoringBacklog._render_detail(proposal))
        except RefactoringProposal.DoesNotExist:
            return HttpResponse(
                '<div class="alert alert-danger">Proposal not found</div>',
                status=404,
            )

    @staticmethod
    @csrf_exempt
    def htmx_update_status(request: HttpRequest, proposal_id: str):
        """Update proposal status."""
        if request.method != 'POST':
            return HttpResponse(status=405)

        try:
            data = json.loads(request.body)
            new_status = data.get('status')

            if new_status not in dict(RefactoringProposal.STATUS_CHOICES):
                return HttpResponse(
                    '<div class="alert alert-danger">Invalid status</div>',
                    status=400,
                )

            proposal = RefactoringProposal.objects.get(proposal_id=proposal_id)
            proposal.status = new_status
            proposal.save()

            return HttpResponse(
                f'<span class="badge bg-{proposal.status_badge_class}">'
                f'{proposal.get_status_display()}</span>'
            )
        except RefactoringProposal.DoesNotExist:
            return HttpResponse(
                '<div class="alert alert-danger">Proposal not found</div>',
                status=404,
            )
        except Exception as e:
            return HttpResponse(
                f'<div class="alert alert-danger">Error: {e}</div>',
                status=500,
            )

    @staticmethod
    def _render_detail(proposal: RefactoringProposal) -> str:
        """Render detailed proposal view."""
        steps_html = ""
        for i, step in enumerate(proposal.steps, 1):
            steps_html += f'<li class="list-group-item">{i}. {step}</li>'

        scope_html = ""
        for service in proposal.scope[:10]:
            scope_html += f'<span class="badge bg-secondary me-1">{service}</span>'
        if len(proposal.scope) > 10:
            scope_html += f'<span class="badge bg-light text-dark">+{len(proposal.scope) - 10} more</span>'

        return f'''
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5 class="mb-0">{proposal.proposal_id}: {proposal.get_proposal_type_display()}</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"
                    onclick="document.getElementById('proposal-detail-modal').style.display='none'"></button>
            </div>
            <div class="card-body">
                <p class="lead">{proposal.summary}</p>

                <div class="row mb-3">
                    <div class="col-md-4">
                        <strong>Impact:</strong>
                        <span class="badge bg-{proposal.impact_badge_class}">{proposal.get_impact_display()}</span>
                    </div>
                    <div class="col-md-4">
                        <strong>Risk:</strong>
                        <span class="badge bg-{proposal.risk_badge_class}">{proposal.get_risk_display()}</span>
                    </div>
                    <div class="col-md-4">
                        <strong>Status:</strong>
                        <span class="badge bg-{proposal.status_badge_class}">{proposal.get_status_display()}</span>
                    </div>
                </div>

                <div class="mb-3">
                    <strong>Affected Services:</strong>
                    <div class="mt-1">{scope_html}</div>
                </div>

                {f'<div class="mb-3"><strong>Root Cause:</strong><p class="text-muted">{proposal.root_cause}</p></div>' if proposal.root_cause else ''}

                <div class="mb-3">
                    <strong>Refactoring Steps:</strong>
                    <ol class="list-group list-group-numbered mt-2">{steps_html}</ol>
                </div>

                {f'<div class="mb-3"><strong>Expected Improvement:</strong><p class="text-muted">{proposal.expected_improvement}</p></div>' if proposal.expected_improvement else ''}

                <div class="mb-3">
                    <strong>Metrics Before:</strong>
                    <ul class="list-unstyled text-muted">
                        {f'<li>SCC Size: {proposal.scc_size_before}</li>' if proposal.scc_size_before else ''}
                        {f'<li>Fan-in: {proposal.fan_in_before:.1f}</li>' if proposal.fan_in_before else ''}
                        {f'<li>Fan-out: {proposal.fan_out_before:.1f}</li>' if proposal.fan_out_before else ''}
                    </ul>
                </div>

                <div class="d-flex gap-2">
                    <button class="btn btn-success btn-sm"
                        hx-post="/htmx/refactoring/{proposal.proposal_id}/status/"
                        hx-vals='{{"status": "approved"}}'
                        hx-target="#status-{proposal.proposal_id}"
                        hx-swap="innerHTML">
                        Approve
                    </button>
                    <button class="btn btn-warning btn-sm"
                        hx-post="/htmx/refactoring/{proposal.proposal_id}/status/"
                        hx-vals='{{"status": "in_progress"}}'
                        hx-target="#status-{proposal.proposal_id}"
                        hx-swap="innerHTML">
                        Start Work
                    </button>
                    <button class="btn btn-secondary btn-sm"
                        hx-post="/htmx/refactoring/{proposal.proposal_id}/status/"
                        hx-vals='{{"status": "rejected"}}'
                        hx-target="#status-{proposal.proposal_id}"
                        hx-swap="innerHTML">
                        Reject
                    </button>
                </div>
            </div>
        </div>
        '''

    @classmethod
    def get_urls(cls):
        return [
            path('refactoring/', cls.htmx_list, name='refactoring_list'),
            path('refactoring/<str:proposal_id>/', cls.htmx_detail, name='refactoring_detail'),
            path('refactoring/<str:proposal_id>/status/', cls.htmx_update_status, name='refactoring_status'),
        ]
