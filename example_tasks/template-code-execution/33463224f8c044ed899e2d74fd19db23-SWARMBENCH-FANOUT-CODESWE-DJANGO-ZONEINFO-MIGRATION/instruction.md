# Django Ticket #32365: zoneinfo should be the default

We're doing the pytz -> zoneinfo migration for Django 4.0.

The codebase currently uses pytz as the default timezone implementation
across core utils, database backends, template tags, docs, and tests.
We need to flip that so zoneinfo is the default path.

- zoneinfo (or backports.zoneinfo on older Python) replaces pytz everywhere.
- pytz is no longer a hard dependency.
- django.utils.timezone.utc should use the standard library UTC.
- Add a transitional setting so existing projects can keep using pytz
  temporarily. Overriding it should trigger a deprecation warning since
  pytz support will be removed in Django 5.0.
- The is_dst parameter should be deprecated wherever it currently appears
  in timezone-aware functions. It should raise a deprecation warning and
  no longer default to None.
- Update all relevant documentation and tests.

Constraints:

- Work in `/testbed`.
- Do not modify files outside the Django source tree and its tests.
- Do not modify `tests/runtests.py` or the test runner infrastructure.
