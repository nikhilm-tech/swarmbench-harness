The NetBox application at `/testbed` has sixteen bugs reported by users and maintainers. They are all independent of each other and scattered across different parts of the codebase. Fix all sixteen.

Bug 1 -- Image attachments overwrite each other on S3 storage

Users uploading image attachments via S3-compatible storage backends report that files with the same name silently overwrite each other instead of being deduplicated. The upload path logic must be refactored so that a helper function `_build_image_attachment_path()` constructs the deterministic path, and the main upload function calls Django's `Storage.get_available_name()` to guarantee collision avoidance regardless of which storage backend is active.

Bug 2 -- ScriptModule save triggers class synchronization twice

Saving a ScriptModule triggers `sync_classes()` twice per save. Investigate the model's `save()` method and any signal handlers connected to ScriptModule's `post_save` signal to identify the redundant invocation, then eliminate it so synchronization happens exactly once.

Bug 3 -- humanize_speed filter shows wrong unit for non-round Gbps/Tbps

The `humanize_speed` template filter renders 2,500,000 Kbps as "2500 Mbps" instead of "2.5 Gbps" and 1,600,000,000 Kbps as "1600 Gbps" instead of "1.6 Tbps". The filter should always display speeds using the largest appropriate unit, including decimal values where the result is not a whole number.

Bug 4 -- Cable CSV bulk import fails for power feed terminations

CSV bulk import of cables fails when one side terminates on a power feed. The cable import form assumes both sides belong to a device, but power feeds belong to power panels. The form needs `side_a_power_panel` and `side_b_power_panel` fields, and its side-cleaning logic must handle `powerfeed` content types by looking up the termination via the power panel rather than a device.

Bug 5 -- Interface speed field overflows above 2.1 Tbps

LAG interfaces with aggregate speed above ~2.1 Tbps cannot be saved because the speed field on the Interface model is a 32-bit integer that overflows at 2,147,483,647. The model field must be widened to a 64-bit `PositiveBigIntegerField`, a corresponding database migration `0227_alter_interface_speed_bigint.py` must be created, all forms and filters that constrain the speed range must be updated to support the wider range (including adding a `MultiValueBigNumberFilter` to the utilities filters), and the GraphQL schema must use a matching BigInt type annotation.

Bug 6 -- Plugin template extensions missing on declarative-layout views

Plugin template extensions registered via `PluginTemplateExtension` do not render on detail pages that were recently converted to declarative layout definitions. The affected views need `PluginContentPanel` slots added for left, right, and full-width positions. Investigate which IPAM and core views were recently migrated to declarative layouts and are now missing these panels.

Bug 7 -- Uploading a faulty script silently registers a broken module

Uploading a custom script file that contains syntax errors or import failures silently registers a broken module in the database, preventing re-upload due to a uniqueness constraint. A `validate_script_content()` function must be created that compiles and executes the uploaded content to verify it is loadable. Both the script file form's clean method and the script module API serializer's validate method must invoke this function before persisting the file.

Bug 8 -- Device-type YAML export omits port-mapping data

When exporting device types or module types to YAML, the output is missing port-mapping entries. The port template mapping model needs a `to_yaml()` method, and the device type and module type YAML export methods must include port-mapping data in their output.

Bug 9 -- Interface CSV export renders connection column with whitespace artifacts

CSV exports of interface tables render the connection column with multi-line template whitespace instead of clean values. The base path endpoint table class and the interface table both need a `value_connection()` method that produces clean CSV-friendly output, with the interface table handling virtual circuit connections specifically.

Bug 10 -- REST API accepts non-existent custom field names in PATCH requests

PATCH requests to the REST API with custom field names that do not actually exist silently succeed, and the bogus names appear in changelogs. The custom fields data serializer field must validate incoming field names against the set of custom fields defined for the object type and raise `ValidationError` for unknown keys. Additionally, the base validated model serializer must preserve any normalization the model's `clean()` method performs on `custom_field_data`.

Bug 11 -- Module type import with port mappings fails on ambiguous port names

Importing module types with port mappings fails with "get() returned more than one" errors when multiple types share similar front/rear port template names. The port template mapping import form needs methods to scope the front and rear port template querysets to the specific device type or module type being imported, preventing cross-type collisions.

Bug 12 -- Custom script "last run" shows creation time, not start time

The "last run" timestamp displayed for custom scripts shows the job's creation time instead of when it actually started executing. Find the mixin that computes the latest job ordering and fix it to order by the job's start time instead of its creation time.

Bug 13 -- API_TOKEN_PEPPERS rejects OrderedDict and other dict subclasses

Setting `API_TOKEN_PEPPERS` to an `OrderedDict` or any other dict subclass raises `ImproperlyConfigured` even though the mapping is perfectly valid. The pepper validation function uses a strict type identity check instead of `isinstance`.

Bug 14 -- Script module Edit button hidden for non-superusers with correct permissions

Non-superusers who have been granted the correct Django model permissions still cannot see the Edit button on the script module listing page. The template checks for a permission name that doesn't match Django's standard `change_scriptmodule` permission naming convention.

Bug 15 -- ColorField widget shows misleading help text about hex input

A model field's `formfield()` method displays help text telling users to enter an RGB hex color manually, but the actual widget is a dropdown color picker that does not accept manual input. The misleading help text should be removed.

Bug 16 -- Contact group "Contacts" count wrong when a contact belongs to multiple nested groups

The contact group list view shows an inflated contact count when a contact is assigned to multiple child groups under the same parent. For example, if one contact is in both `Group A > Subgroup 1` and `Group A > Subgroup 2`, `Group A` counts that contact twice. The current annotation uses django-mptt's `add_related_count()` which cannot deduplicate across the ManyToMany relation. A custom manager with an `annotate_contacts()` method must replace the existing annotation calls. The detail view also double-counts contacts in a similar scenario and needs a `.distinct()` call on the contacts queryset.

Fix all sixteen bugs. Do not modify any files in the `tests/` directory. The repository is at `/testbed`.
