"""
URL patterns for HTMX component endpoints.
Each component registers its own URLs here.
"""
from components.counter.counter import Counter
from components.search.search import Search
from components.quote.quote import Quote
from components.items_list.items_list import ItemsList
from dependencies.components.graph.graph import DependencyGraph
from dependencies.components.refactoring.refactoring import RefactoringBacklog

urlpatterns = []

# Register component URLs
for component_class in [Counter, Search, Quote, ItemsList, DependencyGraph, RefactoringBacklog]:
    if hasattr(component_class, 'get_urls'):
        urlpatterns.extend(component_class.get_urls())
