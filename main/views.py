from django.shortcuts import render


def demo(request):
    """Demo page showcasing HTMX components."""
    return render(request, 'main/demo.html')


def graph(request):
    """Dependency graph visualization page."""
    return render(request, 'main/graph.html')
