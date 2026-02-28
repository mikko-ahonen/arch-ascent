# Claude instructions for arch-ascent

- This file is generated. Add project-specific instructions to `CLAUDE.local.md`.


Architecture dependency analysis


## Type
Django


## Current Phase
**Prototype** - See `docs/claude/prototype.md` for phase-specific instructions.


## Environments


- local - Local development environment running in Docker

  `local` is running in a seperate container, never start a new server in this container either by docker or runserver.



## Key Operations


- The local server is running in a separate container, never start it by `python manage.py runserver`
- `python manage.py test ...` - Run unit and integration tests


- `python manage.py test e2e` - Run E2E tests



## Structure and files

Do not create extra directory structure. Store directories at the repository root. See README.md for organzation.

- All documentation: `docs/` directory    # For all concise, clear, documentation
- Temporary files: `tmp/` directory       # For example test reports, plans, bug fix reports

- Server log: `/src/server.log`


## Development Phases

In general, we work on a specific phase at the time. Phase describes the primary focus, it is informational not normative; anything can be changed at any
time and we can jump back to a phase. Phase may be related to the whole project or later iteratively for a new feature we are working on 
for existing projects.

The phases are:

concept → design → prototype → implement → testing → userguide → e2e → landing → training

There are specific instructions for each phase in `docs/claude/`. Look the corresponding instructions when doing such changes.

- `docs/claude/concept.md` -- Concept phase instructions
- `docs/claude/design.md` -- Design phase instructions
- `docs/claude/prototype.md` -- Prototyping phase instructions
- `docs/claude/implementation.md` -- Implementation and unit testing phase instructions
- `docs/claude/testing.md` -- Integration testing phase instructions
- `docs/claude/e2e.md` -- E2E testing phase instructions

## Tickets

Keep all features, todos, bugs etc. in GitHub tickets. Use skill 'ticket' to access tickets. They may be supplied by users, developers,
or created by you for example based on Sentry issues.


- Access `local` server via URLs. Do not run `python manage.py startserver` or docker commands, they do not work.
- Use `http://arch_ascent:8000` to access the server in the container.
- Use that URL even if I give you an URL using http://localhost:<port> address. It is the same server, I use port forwarding.
- Use `python manage.py test --keepdb` when running tests.
- Access server log from `/src/debug.log`.
- Restart local server using `/restart` endpoint.
- Prefer comments over extensive implementation documents you need during implementation. Such documents are ephemeral and should be stored in tmp/.

- E2E tests use Playwright with Chromium.


