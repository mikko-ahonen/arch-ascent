// Custom JavaScript

// HTMX event handlers
document.addEventListener('htmx:afterSwap', function(evt) {
    // Re-initialize any JS components after HTMX swaps
    console.log('HTMX swap completed:', evt.detail.target);
});

document.addEventListener('htmx:sendError', function(evt) {
    console.error('HTMX request failed:', evt.detail);
});
