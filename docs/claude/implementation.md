# Implementation — Phase Instructions

- This file is generated. Add project-specific instructions to `implementation.local.md` in this directory.
- Write the actual implementation notes in `docs/implementation/`.
- Implementation always needs a proper unit test
- Implementation is not ready until all issues found in unit testing has been fixed
- Before starting to fix a bug, create a proper failing regression test case. Document the issue and important findings in the comments of the regression test
- Don't be lazy. Proper regression test case must not take shortcuts. Do not skip it if test data does not exist, you encounter a tooling issue, 'it 
  cannot be tested' etc.
- Always commit your changes to git after you have properly verified that a fix for a bug works, by running the test case
- Before you start, make sure you understand the security model in `docs/implementation/security.md`.
- Do not make any unsubstantiated claims. Only claim you to you have fixed an issue if you have first made a test case that realistically the tests proves the issue exists, and the test case is failing, and then your fixes makes the test case to pass.
- Always commit your changes to git after an issue has been fixed, or you have created substantial change.

- Use constants for all hard-coded values such as pixel widths and heights

- Track all new major features and bug fixes between released versions in CHANGES.md. Do not include bug fixes that affect only the current, non-released version. The file is ordered in reverse order. Current version is in version.txt and tagged with git. Add new features under the next minor release number.

- For taking screenshots for documentation, see [docs/screenshot-guide.md](docs/screenshot-guide.md)


- Django runs locally in seperate docker container, called 'local'. Never run python manage.py startserver, nor run `python manage.py runserver`. They do not work.
- Use `config/settings.py` for Django settings (config module pattern).
- Use `python manage.py test --keepdb` when running tests.
- Access server log from `/src/debug.log`.
- All strings should be localized (in templates, use trans for single lines and blocktrans for paragraphs). The translations depend on 
  project. By default, no translations.
- Use django messages for any feedback to the customer
- Prefer comments over extensive implementation documents you need during implementation. Such documents are ephemeral and should be stored in tmp/.
- Do not use db_table to configure table names.




## Security

- Security model is typically public/ for public endpoints. Other endpoints must be protected. Default to restrictive security. Require superuser
  for non-public views and other endpoints by default.

## Unit testing

- For unit testing, use django test framework, as it works better with database settings than pytest
- Each view must have a test to verify that the view renders without errors
- Each modification view must have validation unit test to verify that change was made, and to verify what happens on errors
- Test each validation with unit tests
- All view endpoints, including views, must have at least two unit tests: positive test that checks that the endpoint works, and negative test case that checks that the proper authentication is used

## Styling

- Avoid colors. Do not use secondary, info, warning and other bootstrap regular or outline styles in buttons. Always use primary outline buttons.
- Avoid creating extra info/warning boxes. For warnings, use "{% danger %} ... {% danger %}" template tag.
- In form controls and buttons, use primary outline style. Never use secondary or secondary outline style, as it has bad contrast. Also, don't use danger/info/success etc. styles in buttons.
- Instead of Title Case, use Sentence case in buttons and titles.
- Use bootstrap 5 for styling
- Avoid icons in unless they are intentionally already used in that context. Buttons and info boxes should not use icons, unless that component already
  has it. Icons are used mostly in navigations when we want to make a condensed navigation, and when they indicate a status. Default to using bootstrap icons.
- In list views using cards, place action buttons on the footer. Hide less needed buttons in a bootstrap dropdown menu

## Debugging

- When writing debugging information to browser console.log, use JSON.stringify() for the relevant data so that the log contains the whole entities instead of requiring manual expansion
- When you are iterating to fix browser issues, write a frontend version number to the console log and verify that the version number has been updated. Several layers of caching may affect the running version. Django does not recognize changes to Django component templates, but you need to force loading of the templates by touching models.py file or restarting the server.

### Modals

- For all modals use "{% component 'modal' .. " %}" which uses bootstrap modals. Never use Javascript/HTML modals.
- For create/delete/update operations use popup modals with `{% component 'modal' ... %}`.
- Use global modal templates, if possible, under /templates, rather than app-specific or model-specific
- Modal buttons: primary outline style for all buttons (if background is primary outline, use white text instead).
  Use m-1 class for spacing buttons, naturally leave buttons left-align. First action on modals is the primary action, such as "OK". Cancel/Close is the last.
- Open modals with `<button class="btn btn-outline-primary open-popup" href="#" data-popup-url="...">...</button>"
- All validation errors must be rendered inside the modal, using backend validation, unless the component has built in 
  validation mechanism. Disable HTML5 frontend validations.
- On modal success, server should mostly return HX-Refresh: true, so that the enclosing list view gets updated


## Key Commands

- `rs` - Alias for `python manage.py runserver 0.0.0.0:8000`
- `mm` - Alias for `python manage.py makemigrations`
- `mg` - Alias for `python manage.py migrate`


- `pytest e2e/` - Run E2E tests



## Structure

Do not create extra directory structure. Store directories at the repository root.

```
arch-ascent/
├── doc/               # Documentation

├── config/             # Django settings module
├── templates/          # Django global templates
├── static/             # Static files

├── e2e/                # E2E tests (Playwright)


└── tests/              # Test suites
```


## File Locations

- All documentation: `doc/` directory    # For all concise, clear, documentation
- Temporary files: `tmp/` directory      # For example test reports, plans, bug fix reports

- Server log: `/src/debug.log`
