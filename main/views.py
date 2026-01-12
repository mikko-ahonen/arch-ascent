from django.shortcuts import render


def home(request):
    """Home page view."""
    return render(request, 'main/home.html')


def demo(request):
    """Demo page showcasing HTMX components."""
    return render(request, 'main/demo.html')


def graph(request):
    """Dependency graph visualization page."""
    return render(request, 'main/graph.html')
