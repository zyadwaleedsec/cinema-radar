"""Single source of truth for the application version.

The version follows Semantic Versioning (https://semver.org):

* MAJOR - a change users must adapt to (data model, onboarding, removed features).
* MINOR - a new capability that stays backward compatible.
* PATCH - a fix or copy change with no behaviour change.

Release checklist lives in ``docs/TECHNICAL.md``.  Never edit the version in
more than one place: everything reads ``__version__`` from here.
"""

from __future__ import annotations

__version__ = "3.3.0"

#: Displayed in ``/help``, the settings screen and the admin panel.
VERSION = __version__

#: Human readable, used in logs and release notes.
RELEASE_NAME = "Support as often as you like"

__all__ = ["RELEASE_NAME", "VERSION", "__version__"]
