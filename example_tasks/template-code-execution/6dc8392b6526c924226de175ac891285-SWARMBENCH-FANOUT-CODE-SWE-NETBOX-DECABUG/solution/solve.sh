#!/bin/bash
set -e
cd /testbed

###############################################################################
# Bug 1: S3 storage allows duplicate image attachment filenames (#21801)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG1'
diff --git a/netbox/extras/utils.py b/netbox/extras/utils.py
--- a/netbox/extras/utils.py
+++ b/netbox/extras/utils.py
@@ -2,7 +2,7 @@
 from pathlib import Path
 
 from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
-from django.core.files.storage import default_storage
+from django.core.files.storage import Storage, default_storage
 from django.core.files.utils import validate_file_name
 from django.db import models
 from django.db.models import Q
@@ -67,15 +67,13 @@
     return False
 
 
-def image_upload(instance, filename):
+def _build_image_attachment_path(instance, filename, *, storage=default_storage):
     """
-    Return a path for uploading image attachments.
+    Build a deterministic relative path for an image attachment.
 
     - Normalizes browser paths (e.g., C:\\fake_path\\photo.jpg)
     - Uses the instance.name if provided (sanitized to a *basename*, no ext)
     - Prefixes with a machine-friendly identifier
-
-    Note: Relies on Django's default_storage utility.
     """
     upload_dir = 'image-attachments'
     default_filename = 'unnamed'
@@ -92,22 +90,38 @@
     # Rely on Django's get_valid_filename to perform sanitization.
     stem = (instance.name or file_path.stem).strip()
     try:
-        safe_stem = default_storage.get_valid_name(stem)
+        safe_stem = storage.get_valid_name(stem)
     except SuspiciousFileOperation:
         safe_stem = default_filename
 
     # Append the uploaded extension only if it's an allowed image type
-    final_name = f"{safe_stem}.{ext}" if ext in allowed_img_extensions else safe_stem
+    final_name = f'{safe_stem}.{ext}' if ext in allowed_img_extensions else safe_stem
 
     # Create a machine-friendly prefix from the instance
-    prefix = f"{instance.object_type.model}_{instance.object_id}"
-    name_with_path = f"{upload_dir}/{prefix}_{final_name}"
+    prefix = f'{instance.object_type.model}_{instance.object_id}'
+    name_with_path = f'{upload_dir}/{prefix}_{final_name}'
 
     # Validate the generated relative path (blocks absolute/traversal)
     validate_file_name(name_with_path, allow_relative_path=True)
     return name_with_path
 
 
+def image_upload(instance, filename):
+    """
+    Return a relative upload path for an image attachment, applying Django's
+    usual suffix-on-collision behavior regardless of storage backend.
+    """
+    field = instance.image.field
+    name_with_path = _build_image_attachment_path(instance, filename, storage=field.storage)
+
+    # Intentionally call Django's base Storage implementation here. Some
+    # backends override get_available_name() to reuse the incoming name
+    # unchanged, but we want Django's normal suffix-on-collision behavior
+    # while still dispatching exists() / get_alternative_name() to the
+    # configured storage instance.
+    return Storage.get_available_name(field.storage, name_with_path, max_length=field.max_length)
+
+
 def is_script(obj):
     """
     Returns True if the object is a Script or Report.
PATCH_BUG1

###############################################################################
# Bug 2: ScriptModule.save() triggers sync_classes() twice (#21869)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG2'
diff --git a/netbox/extras/models/scripts.py b/netbox/extras/models/scripts.py
--- a/netbox/extras/models/scripts.py
+++ b/netbox/extras/models/scripts.py
@@ -5,8 +5,6 @@
 from django.contrib.contenttypes.fields import GenericRelation
 from django.db import models
 from django.db.models import Q
-from django.db.models.signals import post_save
-from django.dispatch import receiver
 from django.urls import reverse
 from django.utils.translation import gettext_lazy as _
 
@@ -188,9 +186,7 @@
     def save(self, *args, **kwargs):
         self.file_root = ManagedFileRootPathChoices.SCRIPTS
         super().save(*args, **kwargs)
-        self.sync_classes()
-
 
-@receiver(post_save, sender=ScriptModule)
-def script_module_post_save_handler(instance, created, **kwargs):
-    instance.sync_classes()
+        # Sync script classes after the module has been saved. This is the
+        # single intended synchronization path for ScriptModule saves.
+        self.sync_classes()
PATCH_BUG2

###############################################################################
# Bug 3: humanize_speed template filter decimal Gbps/Tbps (#21795)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG3'
diff --git a/netbox/utilities/templatetags/helpers.py b/netbox/utilities/templatetags/helpers.py
--- a/netbox/utilities/templatetags/helpers.py
+++ b/netbox/utilities/templatetags/helpers.py
@@ -186,26 +186,52 @@
     return ActionURLNode(model, action, kwargs, asvar)
 
 
+def _format_speed(speed, divisor, unit):
+    """
+    Format a speed value with a given divisor and unit.
+
+    Handles decimal values and strips trailing zeros for clean output.
+    """
+    whole, remainder = divmod(speed, divisor)
+    if remainder == 0:
+        return f'{whole} {unit}'
+
+    # Divisors are powers of 10, so len(str(divisor)) - 1 matches the decimal precision.
+    precision = len(str(divisor)) - 1
+    fraction = f'{remainder:0{precision}d}'.rstrip('0')
+    return f'{whole}.{fraction} {unit}'
+
+
 @register.filter()
 def humanize_speed(speed):
     """
-    Humanize speeds given in Kbps. Examples:
+    Humanize speeds given in Kbps, always using the largest appropriate unit.
+
+    Decimal values are displayed when the result is not a whole number;
+    trailing zeros after the decimal point are stripped for clean output.
+
+    Examples:
 
-        1544 => "1.544 Mbps"
-        100000 => "100 Mbps"
-        10000000 => "10 Gbps"
+        1_544 => "1.544 Mbps"
+        100_000 => "100 Mbps"
+        1_000_000 => "1 Gbps"
+        2_500_000 => "2.5 Gbps"
+        10_000_000 => "10 Gbps"
+        800_000_000 => "800 Gbps"
+        1_600_000_000 => "1.6 Tbps"
     """
     if not speed:
         return ''
-    if speed >= 1000000000 and speed % 1000000000 == 0:
-        return '{} Tbps'.format(int(speed / 1000000000))
-    if speed >= 1000000 and speed % 1000000 == 0:
-        return '{} Gbps'.format(int(speed / 1000000))
-    if speed >= 1000 and speed % 1000 == 0:
-        return '{} Mbps'.format(int(speed / 1000))
-    if speed >= 1000:
-        return '{} Mbps'.format(float(speed) / 1000)
-    return '{} Kbps'.format(speed)
+
+    speed = int(speed)
+
+    if speed >= 1_000_000_000:
+        return _format_speed(speed, 1_000_000_000, 'Tbps')
+    if speed >= 1_000_000:
+        return _format_speed(speed, 1_000_000, 'Gbps')
+    if speed >= 1_000:
+        return _format_speed(speed, 1_000, 'Mbps')
+    return f'{speed} Kbps'
 
 
 def _humanize_capacity(value, divisor=1000):
PATCH_BUG3

###############################################################################
# Bug 4: Cable CSV bulk import fails for power feed (#21783)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG4'
diff --git a/netbox/dcim/forms/bulk_import.py b/netbox/dcim/forms/bulk_import.py
--- a/netbox/dcim/forms/bulk_import.py
+++ b/netbox/dcim/forms/bulk_import.py
@@ -1409,8 +1409,16 @@
     side_a_device = CSVModelChoiceField(
         label=_('Side A device'),
         queryset=Device.objects.all(),
+        required=False,
         to_field_name='name',
-        help_text=_('Device name')
+        help_text=_('Device name (for device component terminations)')
+    )
+    side_a_power_panel = CSVModelChoiceField(
+        label=_('Side A power panel'),
+        queryset=PowerPanel.objects.all(),
+        required=False,
+        to_field_name='name',
+        help_text=_('Power panel name (for power feed terminations)')
     )
     side_a_type = CSVContentTypeField(
         label=_('Side A type'),
@@ -1434,8 +1442,16 @@
     side_b_device = CSVModelChoiceField(
         label=_('Side B device'),
         queryset=Device.objects.all(),
+        required=False,
+        to_field_name='name',
+        help_text=_('Device name (for device component terminations)')
+    )
+    side_b_power_panel = CSVModelChoiceField(
+        label=_('Side B power panel'),
+        queryset=PowerPanel.objects.all(),
+        required=False,
         to_field_name='name',
-        help_text=_('Device name')
+        help_text=_('Power panel name (for power feed terminations)')
     )
     side_b_type = CSVContentTypeField(
         label=_('Side B type'),
@@ -1490,8 +1506,9 @@
     class Meta:
         model = Cable
         fields = [
-            'side_a_site', 'side_a_device', 'side_a_type', 'side_a_name', 'side_b_site', 'side_b_device', 'side_b_type',
-            'side_b_name', 'type', 'status', 'profile', 'tenant', 'label', 'color', 'length', 'length_unit',
+            'side_a_site', 'side_a_device', 'side_a_power_panel', 'side_a_type', 'side_a_name',
+            'side_b_site', 'side_b_device', 'side_b_power_panel', 'side_b_type', 'side_b_name',
+            'type', 'status', 'profile', 'tenant', 'label', 'color', 'length', 'length_unit',
             'description', 'owner', 'comments', 'tags',
         ]
 
@@ -1501,16 +1518,22 @@
         if data:
             # Limit choices for side_a_device to the assigned side_a_site
             if side_a_site := data.get('side_a_site'):
-                side_a_device_params = {f'site__{self.fields["side_a_site"].to_field_name}': side_a_site}
+                side_a_parent_params = {f'site__{self.fields['side_a_site'].to_field_name}': side_a_site}
                 self.fields['side_a_device'].queryset = self.fields['side_a_device'].queryset.filter(
-                    **side_a_device_params
+                    **side_a_parent_params
+                )
+                self.fields['side_a_power_panel'].queryset = self.fields['side_a_power_panel'].queryset.filter(
+                    **side_a_parent_params
                 )
 
             # Limit choices for side_b_device to the assigned side_b_site
             if side_b_site := data.get('side_b_site'):
-                side_b_device_params = {f'site__{self.fields["side_b_site"].to_field_name}': side_b_site}
+                side_b_parent_params = {f'site__{self.fields['side_b_site'].to_field_name}': side_b_site}
                 self.fields['side_b_device'].queryset = self.fields['side_b_device'].queryset.filter(
-                    **side_b_device_params
+                    **side_b_parent_params
+                )
+                self.fields['side_b_power_panel'].queryset = self.fields['side_b_power_panel'].queryset.filter(
+                    **side_b_parent_params
                 )
 
     def _clean_side(self, side):
@@ -1522,33 +1545,57 @@
         assert side in 'ab', f"Invalid side designation: {side}"
 
         device = self.cleaned_data.get(f'side_{side}_device')
+        power_panel = self.cleaned_data.get(f'side_{side}_power_panel')
         content_type = self.cleaned_data.get(f'side_{side}_type')
         name = self.cleaned_data.get(f'side_{side}_name')
-        if not device or not content_type or not name:
+        if not content_type or not name:
             return None
 
         model = content_type.model_class()
-        try:
-            if (
-                device.virtual_chassis and
-                device.virtual_chassis.master == device and
-                not model.objects.filter(device=device, name=name).exists()
-            ):
-                termination_object = model.objects.get(device__in=device.virtual_chassis.members.all(), name=name)
-            else:
-                termination_object = model.objects.get(device=device, name=name)
-            if termination_object.cable is not None and termination_object.cable != self.instance:
+
+        # PowerFeed terminations reference a PowerPanel, not a Device
+        if content_type.model == 'powerfeed':
+            if not power_panel:
+                return None
+            try:
+                termination_object = model.objects.get(power_panel=power_panel, name=name)
+                if termination_object.cable is not None and termination_object.cable != self.instance:
+                    raise forms.ValidationError(
+                        _("Side {side_upper}: {power_panel} {termination_object} is already connected").format(
+                            side_upper=side.upper(), power_panel=power_panel, termination_object=termination_object
+                        )
+                    )
+            except ObjectDoesNotExist:
                 raise forms.ValidationError(
-                    _("Side {side_upper}: {device} {termination_object} is already connected").format(
-                        side_upper=side.upper(), device=device, termination_object=termination_object
+                    _("{side_upper} side termination not found: {power_panel} {name}").format(
+                        side_upper=side.upper(), power_panel=power_panel, name=name
                     )
                 )
-        except ObjectDoesNotExist:
-            raise forms.ValidationError(
-                _("{side_upper} side termination not found: {device} {name}").format(
-                    side_upper=side.upper(), device=device, name=name
+        else:
+            if not device:
+                return None
+            try:
+                if (
+                    device.virtual_chassis and
+                    device.virtual_chassis.master == device and
+                    not model.objects.filter(device=device, name=name).exists()
+                ):
+                    termination_object = model.objects.get(device__in=device.virtual_chassis.members.all(), name=name)
+                else:
+                    termination_object = model.objects.get(device=device, name=name)
+                if termination_object.cable is not None and termination_object.cable != self.instance:
+                    raise forms.ValidationError(
+                        _("Side {side_upper}: {device} {termination_object} is already connected").format(
+                            side_upper=side.upper(), device=device, termination_object=termination_object
+                        )
+                    )
+            except ObjectDoesNotExist:
+                raise forms.ValidationError(
+                    _("{side_upper} side termination not found: {device} {name}").format(
+                        side_upper=side.upper(), device=device, name=name
+                    )
                 )
-            )
+
         setattr(self.instance, f'{side}_terminations', [termination_object])
         return termination_object
 
PATCH_BUG4

###############################################################################
# Bug 5: Interface speed field 32-bit overflow (#21542)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG5A'
diff --git a/netbox/dcim/models/device_components.py b/netbox/dcim/models/device_components.py
--- a/netbox/dcim/models/device_components.py
+++ b/netbox/dcim/models/device_components.py
@@ -806,7 +806,7 @@
         verbose_name=_('management only'),
         help_text=_('This interface is used only for out-of-band management')
     )
-    speed = models.PositiveIntegerField(
+    speed = models.PositiveBigIntegerField(
         blank=True,
         null=True,
         verbose_name=_('speed (Kbps)')
PATCH_BUG5A

cat > netbox/dcim/migrations/0227_alter_interface_speed_bigint.py <<'MIGRATION'
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('dcim', '0226_modulebay_rebuild_tree'),
    ]

    operations = [
        migrations.AlterField(
            model_name='interface',
            name='speed',
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
    ]
MIGRATION

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG5B'
diff --git a/netbox/utilities/forms/fields/fields.py b/netbox/utilities/forms/fields/fields.py
--- a/netbox/utilities/forms/fields/fields.py
+++ b/netbox/utilities/forms/fields/fields.py
@@ -2,6 +2,7 @@
 
 from django import forms
 from django.conf import settings
+from django.db.models import BigIntegerField as BigIntegerModelField
 from django.db.models import Count
 from django.forms.fields import InvalidJSONInput
 from django.forms.fields import JSONField as _JSONField
@@ -13,17 +14,39 @@
 from utilities.validators import EnhancedURLValidator
 
 __all__ = (
+    'BigIntegerField',
     'ColorField',
     'CommentField',
     'JSONField',
     'LaxURLField',
     'MACAddressField',
+    'PositiveBigIntegerField',
     'QueryField',
     'SlugField',
     'TagFilterField',
 )
 
 
+class BigIntegerField(forms.IntegerField):
+    """
+    An IntegerField constrained to the range of a signed 64-bit integer.
+    """
+    def __init__(self, *args, **kwargs):
+        kwargs.setdefault('min_value', -BigIntegerModelField.MAX_BIGINT - 1)
+        kwargs.setdefault('max_value', BigIntegerModelField.MAX_BIGINT)
+        super().__init__(*args, **kwargs)
+
+
+class PositiveBigIntegerField(BigIntegerField):
+    """
+    An IntegerField constrained to the range supported by Django's
+    PositiveBigIntegerField model field.
+    """
+    def __init__(self, *args, **kwargs):
+        kwargs.setdefault('min_value', 0)
+        super().__init__(*args, **kwargs)
+
+
 class QueryField(forms.CharField):
     """
     A CharField subclass used for global search/query fields in filter forms.
PATCH_BUG5B

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG5C'
diff --git a/netbox/utilities/filters.py b/netbox/utilities/filters.py
--- a/netbox/utilities/filters.py
+++ b/netbox/utilities/filters.py
@@ -7,9 +7,12 @@
 from drf_spectacular.types import OpenApiTypes
 from drf_spectacular.utils import extend_schema_field
 
+from .forms.fields import BigIntegerField
+
 __all__ = (
     'ContentTypeFilter',
     'MultiValueArrayFilter',
+    'MultiValueBigNumberFilter',
     'MultiValueCharFilter',
     'MultiValueContentTypeFilter',
     'MultiValueDateFilter',
@@ -77,6 +80,11 @@
     field_class = multivalue_field_factory(forms.IntegerField)
 
 
+@extend_schema_field(OpenApiTypes.INT64)
+class MultiValueBigNumberFilter(MultiValueNumberFilter):
+    field_class = multivalue_field_factory(BigIntegerField)
+
+
 @extend_schema_field(OpenApiTypes.DECIMAL)
 class MultiValueDecimalFilter(django_filters.MultipleChoiceFilter):
     field_class = multivalue_field_factory(forms.DecimalField)
PATCH_BUG5C

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG5D'
diff --git a/netbox/dcim/filtersets.py b/netbox/dcim/filtersets.py
--- a/netbox/dcim/filtersets.py
+++ b/netbox/dcim/filtersets.py
@@ -26,6 +26,7 @@
 from users.filterset_mixins import OwnerFilterMixin
 from users.models import User
 from utilities.filters import (
+    MultiValueBigNumberFilter,
     MultiValueCharFilter,
     MultiValueContentTypeFilter,
     MultiValueMACAddressFilter,
@@ -2175,7 +2176,7 @@
         distinct=False,
         label=_('LAG interface (ID)'),
     )
-    speed = MultiValueNumberFilter()
+    speed = MultiValueBigNumberFilter(min_value=0)
     duplex = django_filters.MultipleChoiceFilter(
         choices=InterfaceDuplexChoices,
         distinct=False,
PATCH_BUG5D

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG5E'
diff --git a/netbox/dcim/forms/bulk_edit.py b/netbox/dcim/forms/bulk_edit.py
--- a/netbox/dcim/forms/bulk_edit.py
+++ b/netbox/dcim/forms/bulk_edit.py
@@ -20,7 +20,13 @@
 from tenancy.models import Tenant
 from users.models import User
 from utilities.forms import BulkEditForm, add_blank_choice, form_from_model
-from utilities.forms.fields import ColorField, DynamicModelChoiceField, DynamicModelMultipleChoiceField, JSONField
+from utilities.forms.fields import (
+    ColorField,
+    DynamicModelChoiceField,
+    DynamicModelMultipleChoiceField,
+    JSONField,
+    PositiveBigIntegerField,
+)
 from utilities.forms.rendering import FieldSet, InlineFields, TabbedGroups
 from utilities.forms.widgets import BulkEditNullBooleanSelect, NumberWithOptions
 from virtualization.models import Cluster
@@ -1420,7 +1426,7 @@
             'device_id': '$device',
         }
     )
-    speed = forms.IntegerField(
+    speed = PositiveBigIntegerField(
         label=_('Speed'),
         required=False,
         widget=NumberWithOptions(
PATCH_BUG5E

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG5F'
diff --git a/netbox/dcim/forms/filtersets.py b/netbox/dcim/forms/filtersets.py
--- a/netbox/dcim/forms/filtersets.py
+++ b/netbox/dcim/forms/filtersets.py
@@ -19,7 +19,7 @@
 from tenancy.models import Tenant
 from users.models import User
 from utilities.forms import BOOLEAN_WITH_BLANK_CHOICES, FilterForm, add_blank_choice
-from utilities.forms.fields import ColorField, DynamicModelMultipleChoiceField, TagFilterField
+from utilities.forms.fields import ColorField, DynamicModelMultipleChoiceField, PositiveBigIntegerField, TagFilterField
 from utilities.forms.rendering import FieldSet
 from utilities.forms.widgets import NumberWithOptions
 from virtualization.models import Cluster, ClusterGroup, VirtualMachine
@@ -1603,7 +1603,7 @@
         choices=InterfaceTypeChoices,
         required=False
     )
-    speed = forms.IntegerField(
+    speed = PositiveBigIntegerField(
         label=_('Speed'),
         required=False,
         widget=NumberWithOptions(
PATCH_BUG5F

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG5G'
diff --git a/netbox/dcim/graphql/filters.py b/netbox/dcim/graphql/filters.py
--- a/netbox/dcim/graphql/filters.py
+++ b/netbox/dcim/graphql/filters.py
@@ -47,7 +47,13 @@
         VRFFilter,
     )
     from netbox.graphql.enums import ColorEnum
-    from netbox.graphql.filter_lookups import FloatLookup, IntegerArrayLookup, IntegerLookup, TreeNodeFilter
+    from netbox.graphql.filter_lookups import (
+        BigIntegerLookup,
+        FloatLookup,
+        IntegerArrayLookup,
+        IntegerLookup,
+        TreeNodeFilter,
+    )
     from users.graphql.filters import UserFilter
     from virtualization.graphql.filters import ClusterFilter
     from vpn.graphql.filters import L2VPNFilter, TunnelTerminationFilter
@@ -519,7 +525,7 @@
         strawberry_django.filter_field()
     )
     mgmt_only: FilterLookup[bool] | None = strawberry_django.filter_field()
-    speed: Annotated['IntegerLookup', strawberry.lazy('netbox.graphql.filter_lookups')] | None = (
+    speed: Annotated['BigIntegerLookup', strawberry.lazy('netbox.graphql.filter_lookups')] | None = (
         strawberry_django.filter_field()
     )
     duplex: BaseFilterLookup[Annotated['InterfaceDuplexEnum', strawberry.lazy('dcim.graphql.enums')]] | None = (
PATCH_BUG5G

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG5H'
diff --git a/netbox/dcim/graphql/types.py b/netbox/dcim/graphql/types.py
--- a/netbox/dcim/graphql/types.py
+++ b/netbox/dcim/graphql/types.py
@@ -433,6 +433,7 @@
 )
 class InterfaceType(IPAddressesMixin, ModularComponentType, CabledObjectMixin, PathEndpointMixin):
     _name: str
+    speed: BigInt | None
     wwn: str | None
     parent: Annotated["InterfaceType", strawberry.lazy('dcim.graphql.types')] | None
     bridge: Annotated["InterfaceType", strawberry.lazy('dcim.graphql.types')] | None
PATCH_BUG5H

###############################################################################
# Bug 6: Plugin content panels on declarative views (#21913)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG6A'
diff --git a/netbox/ipam/views.py b/netbox/ipam/views.py
--- a/netbox/ipam/views.py
+++ b/netbox/ipam/views.py
@@ -16,6 +16,7 @@
     CommentsPanel,
     ContextTablePanel,
     ObjectsTablePanel,
+    PluginContentPanel,
     RelatedObjectsPanel,
     TemplatePanel,
 )
@@ -55,11 +56,13 @@
             layout.Column(
                 panels.VRFPanel(),
                 TagsPanel(),
+                PluginContentPanel('left_page'),
             ),
             layout.Column(
                 RelatedObjectsPanel(),
                 CustomFieldsPanel(),
                 CommentsPanel(),
+                PluginContentPanel('right_page'),
             ),
         ),
         layout.Row(
@@ -70,6 +73,11 @@
                 ContextTablePanel('export_targets_table', title=_('Export route targets')),
             ),
         ),
+        layout.Row(
+            layout.Column(
+                PluginContentPanel('full_width_page'),
+            ),
+        ),
     )
 
     def get_extra_context(self, request, instance):
@@ -169,10 +177,12 @@
             layout.Column(
                 panels.RouteTargetPanel(),
                 TagsPanel(),
+                PluginContentPanel('left_page'),
             ),
             layout.Column(
                 CustomFieldsPanel(),
                 CommentsPanel(),
+                PluginContentPanel('right_page'),
             ),
         ),
         layout.Row(
@@ -207,6 +217,11 @@
             ),
         ),
+        layout.Row(
+            layout.Column(
+                PluginContentPanel('full_width_page'),
+            ),
+        ),
     )
PATCH_BUG6A

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG6B'
diff --git a/netbox/core/views.py b/netbox/core/views.py
--- a/netbox/core/views.py
+++ b/netbox/core/views.py
@@ -192,6 +192,12 @@
             layout.Column(
                 panels.DataFilePanel(),
                 panels.DataFileContentPanel(),
+                PluginContentPanel('left_page'),
+            ),
+        ),
+        layout.Row(
+            layout.Column(
+                PluginContentPanel('full_width_page'),
             ),
         ),
     )
@@ -253,6 +259,12 @@
         layout.Row(
             layout.Column(
                 ContextTablePanel('table', title=_('Log Entries')),
+                PluginContentPanel('left_page'),
+            ),
+        ),
+        layout.Row(
+            layout.Column(
+                PluginContentPanel('full_width_page'),
             ),
         ),
     )
@@ -393,6 +405,12 @@
             layout.Column(
                 TemplatePanel('core/panels/configrevision_data.html'),
                 TemplatePanel('core/panels/configrevision_comment.html'),
+                PluginContentPanel('left_page'),
+            ),
+        ),
+        layout.Row(
+            layout.Column(
+                PluginContentPanel('full_width_page'),
             ),
         ),
     )
PATCH_BUG6B

###############################################################################
# Bug 7: Faulty script silently registered (#21737)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG7A'
diff --git a/netbox/extras/utils.py b/netbox/extras/utils.py
--- a/netbox/extras/utils.py
+++ b/netbox/extras/utils.py
@@ -1,4 +1,5 @@
 import importlib
+import types
 from pathlib import Path
 
 from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
@@ -21,6 +22,7 @@
     'is_script',
     'is_taggable',
     'run_validators',
+    'validate_script_content',
 )
 
 
@@ -134,6 +136,17 @@
         return False
 
 
+def validate_script_content(content, filename):
+    """
+    Validate that the given content can be loaded as a Python module by compiling
+    and executing it. Raises an exception if the script cannot be loaded.
+    """
+    code = compile(content, filename, 'exec')
+    module_name = Path(filename).stem
+    module = types.ModuleType(module_name)
+    exec(code, module.__dict__)
+
+
 def is_report(obj):
     """
     Returns True if the given object is a Report.
PATCH_BUG7A

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG7B'
diff --git a/netbox/extras/api/serializers_/scripts.py b/netbox/extras/api/serializers_/scripts.py
--- a/netbox/extras/api/serializers_/scripts.py
+++ b/netbox/extras/api/serializers_/scripts.py
@@ -9,6 +9,7 @@
 from core.api.serializers_.jobs import JobSerializer
 from core.choices import ManagedFileRootPathChoices
 from extras.models import Script, ScriptModule
+from extras.utils import validate_script_content
 from netbox.api.serializers import ValidatedModelSerializer
 from utilities.datetime import local_now
 
@@ -39,6 +40,15 @@
         data = super().validate(data)
         data.pop('file_root', None)
         if file is not None:
+            # Validate that the uploaded script can be loaded as a Python module
+            content = file.read()
+            file.seek(0)
+            try:
+                validate_script_content(content, file.name)
+            except Exception as e:
+                raise serializers.ValidationError(
+                    _("Error loading script: {error}").format(error=e)
+                )
             data['file'] = file
         return data
 
diff --git a/netbox/extras/forms/scripts.py b/netbox/extras/forms/scripts.py
--- a/netbox/extras/forms/scripts.py
+++ b/netbox/extras/forms/scripts.py
@@ -4,6 +4,7 @@
 
 from core.choices import JobIntervalChoices
 from core.forms import ManagedFileForm
+from extras.utils import validate_script_content
 from utilities.datetime import local_now
 from utilities.forms.widgets import DateTimePicker, NumberWithOptions
 
@@ -64,6 +65,22 @@
     """
     ManagedFileForm with a custom save method to use django-storages.
     """
+    def clean(self):
+        super().clean()
+
+        if upload_file := self.cleaned_data.get('upload_file'):
+            # Validate that the uploaded script can be loaded as a Python module
+            content = upload_file.read()
+            upload_file.seek(0)
+            try:
+                validate_script_content(content, upload_file.name)
+            except Exception as e:
+                raise forms.ValidationError(
+                    _("Error loading script: {error}").format(error=e)
+                )
+
+        return self.cleaned_data
+
     def save(self, *args, **kwargs):
         # If a file was uploaded, save it to disk
         if self.cleaned_data['upload_file']:
PATCH_BUG7B

###############################################################################
# Bug 8: Device-type YAML export missing port mappings (#21704)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG8'
diff --git a/netbox/dcim/models/device_component_templates.py b/netbox/dcim/models/device_component_templates.py
--- a/netbox/dcim/models/device_component_templates.py
+++ b/netbox/dcim/models/device_component_templates.py
@@ -549,6 +549,14 @@
         self.module_type = self.front_port.module_type
         super().save(*args, **kwargs)
 
+    def to_yaml(self):
+        return {
+            'front_port': self.front_port.name,
+            'front_port_position': self.front_port_position,
+            'rear_port': self.rear_port.name,
+            'rear_port_position': self.rear_port_position,
+        }
+
 
 class FrontPortTemplate(ModularComponentTemplateModel):
     """
diff --git a/netbox/dcim/models/devices.py b/netbox/dcim/models/devices.py
--- a/netbox/dcim/models/devices.py
+++ b/netbox/dcim/models/devices.py
@@ -275,6 +275,15 @@
             data['rear-ports'] = [
                 c.to_yaml() for c in self.rearporttemplates.all()
             ]
+
+        # Port mappings
+        port_mapping_data = [
+            c.to_yaml() for c in self.port_mappings.all()
+        ]
+
+        if port_mapping_data:
+            data['port-mappings'] = port_mapping_data
+
         if self.modulebaytemplates.exists():
             data['module-bays'] = [
                 c.to_yaml() for c in self.modulebaytemplates.all()
diff --git a/netbox/dcim/models/modules.py b/netbox/dcim/models/modules.py
--- a/netbox/dcim/models/modules.py
+++ b/netbox/dcim/models/modules.py
@@ -192,6 +192,14 @@
                 c.to_yaml() for c in self.rearporttemplates.all()
             ]
 
+        # Port mappings
+        port_mapping_data = [
+            c.to_yaml() for c in self.port_mappings.all()
+        ]
+
+        if port_mapping_data:
+            data['port-mappings'] = port_mapping_data
+
         return yaml.dump(dict(data), sort_keys=False)
 
 
PATCH_BUG8

###############################################################################
# Bug 9: Interface CSV export connection column whitespace (#21845)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG10'
diff --git a/netbox/dcim/tables/devices.py b/netbox/dcim/tables/devices.py
--- a/netbox/dcim/tables/devices.py
+++ b/netbox/dcim/tables/devices.py
@@ -382,6 +382,17 @@
         orderable=False
     )
 
+    def value_connection(self, value):
+        if value:
+            connections = []
+            for termination in value:
+                if hasattr(termination, 'parent_object'):
+                    connections.append(f'{termination.parent_object} > {termination}')
+                else:
+                    connections.append(str(termination))
+            return ', '.join(connections)
+        return None
+
 
 class ConsolePortTable(ModularDeviceComponentTable, PathEndpointTable):
     device = tables.Column(
@@ -683,6 +694,15 @@
         orderable=False
     )
 
+    def value_connection(self, record, value):
+        if record.is_virtual and hasattr(record, 'virtual_circuit_termination') and record.virtual_circuit_termination:
+            connections = [
+                f"{t.interface.parent_object} > {t.interface} via {t.parent_object}"
+                for t in record.connected_endpoints
+            ]
+            return ', '.join(connections)
+        return super().value_connection(value)
+
     class Meta(DeviceComponentTable.Meta):
         model = models.Interface
         fields = (
PATCH_BUG10

###############################################################################
# Bug 10: API accepts non-existent custom fields in changelog (#21529)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG11'
diff --git a/netbox/extras/api/customfields.py b/netbox/extras/api/customfields.py
--- a/netbox/extras/api/customfields.py
+++ b/netbox/extras/api/customfields.py
@@ -85,8 +85,18 @@
                 "values."
             )
 
+        custom_fields = {cf.name: cf for cf in self._get_custom_fields()}
+
+        # Reject any unknown custom field names
+        invalid_fields = set(data) - set(custom_fields)
+        if invalid_fields:
+            raise ValidationError({
+                field: _("Custom field '{name}' does not exist for this object type.").format(name=field)
+                for field in sorted(invalid_fields)
+            })
+
         # Serialize object and multi-object values
-        for cf in self._get_custom_fields():
+        for cf in custom_fields.values():
             if cf.name in data and data[cf.name] not in CUSTOMFIELD_EMPTY_VALUES and cf.type in (
                     CustomFieldTypeChoices.TYPE_OBJECT,
                     CustomFieldTypeChoices.TYPE_MULTIOBJECT
diff --git a/netbox/netbox/api/serializers/base.py b/netbox/netbox/api/serializers/base.py
--- a/netbox/netbox/api/serializers/base.py
+++ b/netbox/netbox/api/serializers/base.py
@@ -95,9 +95,6 @@
 
         attrs = data.copy()
 
-        # Remove custom field data (if any) prior to model validation
-        attrs.pop('custom_fields', None)
-
         # Skip ManyToManyFields
         opts = self.Meta.model._meta
         m2m_values = {}
@@ -116,4 +113,8 @@
         # Skip uniqueness validation of individual fields inside `full_clean()` (this is handled by the serializer)
         instance.full_clean(validate_unique=False)
 
+        # Preserve any normalization performed by model.clean() (e.g. stale custom field pruning)
+        if 'custom_field_data' in attrs:
+            data['custom_field_data'] = instance.custom_field_data
+
         return data
PATCH_BUG11

###############################################################################
# Bug 11: Port mapping import with module placeholders (#21683)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG12'
diff --git a/netbox/dcim/forms/object_import.py b/netbox/dcim/forms/object_import.py
--- a/netbox/dcim/forms/object_import.py
+++ b/netbox/dcim/forms/object_import.py
@@ -150,9 +150,25 @@
     class Meta:
         model = PortTemplateMapping
         fields = [
-            'front_port', 'front_port_position', 'rear_port', 'rear_port_position',
+            'device_type', 'module_type', 'front_port', 'front_port_position', 'rear_port', 'rear_port_position',
         ]
 
+    def clean_device_type(self):
+        if device_type := self.cleaned_data['device_type']:
+            front_port = self.fields['front_port']
+            rear_port = self.fields['rear_port']
+            front_port.queryset = front_port.queryset.filter(device_type=device_type)
+            rear_port.queryset = rear_port.queryset.filter(device_type=device_type)
+        return device_type
+
+    def clean_module_type(self):
+        if module_type := self.cleaned_data['module_type']:
+            front_port = self.fields['front_port']
+            rear_port = self.fields['rear_port']
+            front_port.queryset = front_port.queryset.filter(module_type=module_type)
+            rear_port.queryset = rear_port.queryset.filter(module_type=module_type)
+        return module_type
+
 
 class ModuleBayTemplateImportForm(forms.ModelForm):
 
PATCH_BUG12

###############################################################################
# Bug 12: Custom script "last run" shows creation time (#21814)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG13'
diff --git a/netbox/netbox/models/features.py b/netbox/netbox/models/features.py
--- a/netbox/netbox/models/features.py
+++ b/netbox/netbox/models/features.py
@@ -467,7 +467,7 @@
         """
         Return a list of the most recent jobs for this instance.
         """
-        return self.jobs.filter(status__in=JobStatusChoices.TERMINAL_STATE_CHOICES).order_by('-created').defer('data')
+        return self.jobs.filter(status__in=JobStatusChoices.TERMINAL_STATE_CHOICES).order_by('-started').defer('data')
 
 
 class JournalingMixin(models.Model):
PATCH_BUG13

###############################################################################
# Bug 13: API_TOKEN_PEPPERS rejects OrderedDict (#21875)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG14'
diff --git a/netbox/utilities/security.py b/netbox/utilities/security.py
--- a/netbox/utilities/security.py
+++ b/netbox/utilities/security.py
@@ -9,7 +9,7 @@
     """
     Validate the given dictionary of cryptographic peppers for type & sufficient length.
     """
-    if type(peppers) is not dict:
+    if not isinstance(peppers, dict):
         raise ImproperlyConfigured("API_TOKEN_PEPPERS must be a dictionary.")
     for key, pepper in peppers.items():
         if type(key) is not int:
PATCH_BUG14

###############################################################################
# Bug 14: Script module edit button hidden for non-superusers (#21841)
###############################################################################
sed -i 's/perms\.extras\.edit_scriptmodule/perms.extras.change_scriptmodule/g' \
    netbox/templates/extras/inc/script_list_content.html

###############################################################################
# Bug 15: ColorField misleading help text (#21835)
###############################################################################
sed -i '/from django\.utils\.safestring import mark_safe/d' netbox/utilities/fields.py
sed -i "/kwargs\['help_text'\] = mark_safe/d" netbox/utilities/fields.py

###############################################################################
# Bug 16: Contact group "Contacts" count wrong with multi-assignment (#21538)
###############################################################################
patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG16A'
diff --git a/netbox/tenancy/models/contacts.py b/netbox/tenancy/models/contacts.py
--- a/netbox/tenancy/models/contacts.py
+++ b/netbox/tenancy/models/contacts.py
@@ -1,12 +1,14 @@
 from django.contrib.contenttypes.fields import GenericForeignKey
 from django.core.exceptions import ValidationError
 from django.db import models
+from django.db.models.expressions import RawSQL
 from django.urls import reverse
 from django.utils.translation import gettext_lazy as _
 
 from netbox.models import ChangeLoggedModel, NestedGroupModel, OrganizationalModel, PrimaryModel
 from netbox.models.features import CustomFieldsMixin, ExportTemplatesMixin, TagsMixin, has_feature
 from tenancy.choices import *
+from utilities.mptt import TreeManager
 
 __all__ = (
     'Contact',
@@ -16,10 +18,34 @@
 )
 
 
+class ContactGroupManager(TreeManager):
+
+    def annotate_contacts(self):
+        """
+        Annotate the total number of Contacts belonging to each ContactGroup.
+
+        This returns both direct children and children of child groups. Raw SQL is used here to avoid double-counting
+        contacts which are assigned to multiple child groups of the parent.
+        """
+        return self.annotate(
+            contact_count=RawSQL(
+                "SELECT COUNT(DISTINCT m2m.contact_id)"
+                " FROM tenancy_contact_groups m2m"
+                " INNER JOIN tenancy_contactgroup cg ON m2m.contactgroup_id = cg.id"
+                " WHERE cg.tree_id = tenancy_contactgroup.tree_id"
+                " AND cg.lft >= tenancy_contactgroup.lft"
+                " AND cg.lft <= tenancy_contactgroup.rght",
+                ()
+            )
+        )
+
+
 class ContactGroup(NestedGroupModel):
     """
     An arbitrary collection of Contacts.
     """
+    objects = ContactGroupManager()
+
     class Meta:
         ordering = ['name']
         # Empty tuple triggers Django migration detection for MPTT indexes
PATCH_BUG16A

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG16B'
diff --git a/netbox/tenancy/api/views.py b/netbox/tenancy/api/views.py
--- a/netbox/tenancy/api/views.py
+++ b/netbox/tenancy/api/views.py
@@ -42,13 +42,7 @@
 #
 
 class ContactGroupViewSet(MPTTLockedMixin, NetBoxModelViewSet):
-    queryset = ContactGroup.objects.add_related_count(
-        ContactGroup.objects.all(),
-        Contact,
-        'groups',
-        'contact_count',
-        cumulative=True
-    )
+    queryset = ContactGroup.objects.annotate_contacts()
     serializer_class = serializers.ContactGroupSerializer
     filterset_class = filtersets.ContactGroupFilterSet
 
PATCH_BUG16B

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG16C'
diff --git a/netbox/tenancy/views.py b/netbox/tenancy/views.py
--- a/netbox/tenancy/views.py
+++ b/netbox/tenancy/views.py
@@ -205,13 +205,7 @@
 
 @register_model_view(ContactGroup, 'list', path='', detail=False)
 class ContactGroupListView(generic.ObjectListView):
-    queryset = ContactGroup.objects.add_related_count(
-        ContactGroup.objects.all(),
-        Contact,
-        'groups',
-        'contact_count',
-        cumulative=True
-    )
+    queryset = ContactGroup.objects.annotate_contacts()
     filterset = filtersets.ContactGroupFilterSet
     filterset_form = forms.ContactGroupFilterForm
     table = tables.ContactGroupTable
@@ -280,13 +274,7 @@
 
 @register_model_view(ContactGroup, 'bulk_edit', path='edit', detail=False)
 class ContactGroupBulkEditView(generic.BulkEditView):
-    queryset = ContactGroup.objects.add_related_count(
-        ContactGroup.objects.all(),
-        Contact,
-        'groups',
-        'contact_count',
-        cumulative=True
-    )
+    queryset = ContactGroup.objects.annotate_contacts()
     filterset = filtersets.ContactGroupFilterSet
     table = tables.ContactGroupTable
     form = forms.ContactGroupBulkEditForm
@@ -300,13 +288,7 @@
 
 @register_model_view(ContactGroup, 'bulk_delete', path='delete', detail=False)
 class ContactGroupBulkDeleteView(generic.BulkDeleteView):
-    queryset = ContactGroup.objects.add_related_count(
-        ContactGroup.objects.all(),
-        Contact,
-        'groups',
-        'contact_count',
-        cumulative=True
-    )
+    queryset = ContactGroup.objects.annotate_contacts()
     filterset = filtersets.ContactGroupFilterSet
     table = tables.ContactGroupTable
 
PATCH_BUG16C

patch -p1 --forward --no-backup-if-mismatch <<'PATCH_BUG16D'
diff --git a/netbox/tenancy/views.py b/netbox/tenancy/views.py
--- a/netbox/tenancy/views.py
+++ b/netbox/tenancy/views.py
@@ -248,7 +248,7 @@
                 request,
                 groups,
                 extra=(
-                    (Contact.objects.restrict(request.user, 'view').filter(groups__in=groups), 'group_id'),
+                    (Contact.objects.restrict(request.user, 'view').filter(groups__in=groups).distinct(), 'group_id'),
                 ),
             ),
         }
PATCH_BUG16D

echo "All 16 patches applied successfully."
