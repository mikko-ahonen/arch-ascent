# Design — Phase Instructions

- This file is generated. Add project-specific instructions to `design.local.md` in this directory.
- Write the actual design document in `docs/design/design.md`.
- The aim of design phase is to specify the approach used to implement the concept.
- Design must be short, concise, and clear. Use additional files in `docs/design/` for historical background, context, etc. if relevant.
- Also document the reasons why something was done.


- For projects having more than two apps, create a specific design doc in docs/design/<app>.md, and refer to it from docs/design/design.md.
- Always prefer HTMX, Alpine.JS, Django Components over REST APIs and Javascript-heavy code. The views used by the Django component should
  use views defined in the component. 
- Use django forms for validation
- For generic things (modals, typeaheads, etc.) must use a generic Django component that you either create, use or extend
- For others, prefer app-specific Django components
- Views should mostly contain headers, footers, etc. and call the components
