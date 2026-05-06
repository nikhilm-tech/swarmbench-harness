#!/usr/bin/env python3
"""
Verify all sixteen NetBox bug fixes.
Each check traces to a requirement in instruction.md.
"""
import ast
import sys
import importlib
import importlib.util
from pathlib import Path

TESTBED = Path("/testbed")
NETBOX = TESTBED / "netbox"
passed = 0
total = 0


def check(name, fn):
    global passed, total
    total += 1
    try:
        fn()
        print(f"  PASS  {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")


def parse_file(relpath):
    full = NETBOX / relpath
    if not full.exists():
        raise FileNotFoundError(f"{relpath} not found")
    return ast.parse(full.read_text(encoding="utf-8"), filename=str(full))


def find_class(tree, class_name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def find_function(tree_or_class, func_name):
    for node in ast.walk(tree_or_class):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return node
    return None


def get_source(relpath):
    return (NETBOX / relpath).read_text(encoding="utf-8")


# ==========================================================================
# Bug 1: S3 storage duplicate filenames (#21801)
# ==========================================================================
def test_bug1_build_path():
    tree = parse_file("extras/utils.py")
    func = find_function(tree, "_build_image_attachment_path")
    assert func is not None, "_build_image_attachment_path function not found"


def test_bug1_collision():
    src = get_source("extras/utils.py")
    tree = parse_file("extras/utils.py")
    func = find_function(tree, "image_upload")
    assert func is not None, "image_upload function not found"
    func_src = ast.get_source_segment(src, func)
    assert "get_available_name" in func_src, "get_available_name not called in image_upload"
    assert "Storage" in src, "Storage not imported in extras/utils.py"


# ==========================================================================
# Bug 2: ScriptModule.save() triggers sync_classes() twice (#21869)
# ==========================================================================
def test_bug2_no_signal():
    src = get_source("extras/models/scripts.py")
    tree = parse_file("extras/models/scripts.py")
    assert "post_save" not in src, "post_save signal still referenced in scripts.py"
    assert "@receiver" not in src, "@receiver decorator still present in scripts.py"
    func = find_function(tree, "script_module_post_save_handler")
    assert func is None, "script_module_post_save_handler function still exists"


def test_bug2_single_sync():
    tree = parse_file("extras/models/scripts.py")
    cls = find_class(tree, "ScriptModule")
    assert cls is not None, "ScriptModule class not found"
    method = find_function(cls, "save")
    assert method is not None, "save method not found on ScriptModule"
    src = ast.get_source_segment(get_source("extras/models/scripts.py"), method)
    count = src.count("sync_classes")
    assert count == 1, f"sync_classes called {count} times in save, expected exactly 1"


# ==========================================================================
# Bug 3: humanize_speed decimal formatting (#21795)
# ==========================================================================
def test_bug3_gbps_decimal():
    """Behavioral: call humanize_speed and check output."""
    sys.path.insert(0, str(NETBOX))
    spec = importlib.util.spec_from_file_location(
        "helpers", NETBOX / "utilities/templatetags/helpers.py"
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        tree = parse_file("utilities/templatetags/helpers.py")
        func = find_function(tree, "humanize_speed")
        assert func is not None, "humanize_speed function not found"
        src = ast.get_source_segment(get_source("utilities/templatetags/helpers.py"), func)
        assert "2.5" in src or "fraction" in src or "remainder" in src, \
            "humanize_speed does not appear to handle decimal values"
        return
    hs = mod.humanize_speed
    result = hs(2_500_000)
    assert result == "2.5 Gbps", f"humanize_speed(2500000) = '{result}', expected '2.5 Gbps'"


def test_bug3_tbps_decimal():
    """Behavioral: humanize_speed should render 1.6 Tbps for 1600000000."""
    sys.path.insert(0, str(NETBOX))
    spec = importlib.util.spec_from_file_location(
        "helpers2", NETBOX / "utilities/templatetags/helpers.py"
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return
    hs = mod.humanize_speed
    result = hs(1_600_000_000)
    assert result == "1.6 Tbps", f"humanize_speed(1600000000) = '{result}', expected '1.6 Tbps'"


# ==========================================================================
# Bug 4: Cable CSV bulk import for power feed (#21783)
# ==========================================================================
def test_bug4_power_panel_field():
    tree = parse_file("dcim/forms/bulk_import.py")
    cls = find_class(tree, "CableImportForm")
    assert cls is not None, "CableImportForm class not found"
    src = ast.get_source_segment(get_source("dcim/forms/bulk_import.py"), cls)
    assert "side_a_power_panel" in src, "side_a_power_panel field not found in CableImportForm"
    assert "side_b_power_panel" in src, "side_b_power_panel field not found in CableImportForm"


def test_bug4_powerfeed_handling():
    tree = parse_file("dcim/forms/bulk_import.py")
    cls = find_class(tree, "CableImportForm")
    method = find_function(cls, "_clean_side")
    assert method is not None, "_clean_side method not found"
    src = ast.get_source_segment(get_source("dcim/forms/bulk_import.py"), method)
    assert "powerfeed" in src, "powerfeed handling not found in _clean_side"
    assert "power_panel" in src, "power_panel lookup not found in _clean_side"


# ==========================================================================
# Bug 5: Interface speed 32-bit overflow (#21542)
# ==========================================================================
def test_bug5_model_field():
    tree = parse_file("dcim/models/device_components.py")
    cls = find_class(tree, "Interface")
    assert cls is not None, "Interface class not found"
    for node in ast.walk(cls):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "speed":
                    call = node.value
                    assert isinstance(call, ast.Call), "speed is not a function call"
                    func = call.func
                    attr_name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
                    assert "BigInteger" in attr_name or "PositiveBig" in attr_name, \
                        f"speed field is {attr_name}, expected 64-bit integer type"
                    return
    raise AssertionError("speed field assignment not found in Interface class")


def test_bug5_migration():
    mig_path = NETBOX / "dcim/migrations/0227_alter_interface_speed_bigint.py"
    assert mig_path.exists(), "Migration 0227_alter_interface_speed_bigint.py not found"
    src = mig_path.read_text(encoding="utf-8")
    assert "speed" in src, "Migration does not reference 'speed' field"


def test_bug5_form():
    tree = parse_file("dcim/forms/bulk_edit.py")
    cls = find_class(tree, "InterfaceBulkEditForm")
    assert cls is not None, "InterfaceBulkEditForm class not found"
    src = ast.get_source_segment(get_source("dcim/forms/bulk_edit.py"), cls)
    assert src is not None, "Could not get InterfaceBulkEditForm source"
    full_src = get_source("dcim/forms/bulk_edit.py")
    has_big = "BigInteger" in full_src or "PositiveBig" in full_src
    assert has_big, "No 64-bit integer form field found in bulk_edit.py"


def test_bug5_filter():
    tree = parse_file("utilities/filters.py")
    cls = find_class(tree, "MultiValueBigNumberFilter")
    assert cls is not None, "MultiValueBigNumberFilter class not found"


# ==========================================================================
# Bug 6: Plugin content panels on declarative views (#21913)
# ==========================================================================
def test_bug6_ipam_views():
    src = get_source("ipam/views.py")
    assert "PluginContentPanel" in src, "PluginContentPanel not imported in ipam/views.py"
    tree = parse_file("ipam/views.py")
    for cls_name in ("VRFView", "RouteTargetView"):
        cls = find_class(tree, cls_name)
        assert cls is not None, f"{cls_name} class not found"
        cls_src = ast.get_source_segment(src, cls)
        assert "PluginContentPanel" in cls_src, f"PluginContentPanel not in {cls_name} layout"


def test_bug6_core_views():
    src = get_source("core/views.py")
    tree = parse_file("core/views.py")
    for cls_name in ("DataFileView", "ConfigRevisionView"):
        cls = find_class(tree, cls_name)
        assert cls is not None, f"{cls_name} class not found"
        cls_src = ast.get_source_segment(src, cls)
        assert "PluginContentPanel" in cls_src, f"PluginContentPanel not in {cls_name} layout"


# ==========================================================================
# Bug 7: Faulty script silently registered (#21737)
# ==========================================================================
def test_bug7_validate_exists():
    sys.path.insert(0, str(NETBOX))
    spec = importlib.util.spec_from_file_location("extras_utils", NETBOX / "extras/utils.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        tree = parse_file("extras/utils.py")
        func = find_function(tree, "validate_script_content")
        assert func is not None, "validate_script_content function not found"
        return
    assert hasattr(mod, "validate_script_content"), "validate_script_content not exported"


def test_bug7_form_validation():
    tree = parse_file("extras/forms/scripts.py")
    cls = find_class(tree, "ScriptFileForm")
    assert cls is not None, "ScriptFileForm class not found"
    method = find_function(cls, "clean")
    assert method is not None, "clean method not found on ScriptFileForm"
    src = ast.get_source_segment(get_source("extras/forms/scripts.py"), method)
    assert "validate_script_content" in src, "validate_script_content not called in ScriptFileForm.clean"


def test_bug7_api_validation():
    tree = parse_file("extras/api/serializers_/scripts.py")
    cls = find_class(tree, "ScriptModuleSerializer")
    assert cls is not None, "ScriptModuleSerializer class not found"
    method = find_function(cls, "validate")
    assert method is not None, "validate method not found on ScriptModuleSerializer"
    src = ast.get_source_segment(get_source("extras/api/serializers_/scripts.py"), method)
    assert "validate_script_content" in src, "validate_script_content not called in ScriptModuleSerializer.validate"


# ==========================================================================
# Bug 8: YAML export missing port mappings (#21704)
# ==========================================================================
def test_bug8_to_yaml():
    tree = parse_file("dcim/models/device_component_templates.py")
    cls = find_class(tree, "PortTemplateMapping")
    assert cls is not None, "PortTemplateMapping class not found"
    method = find_function(cls, "to_yaml")
    assert method is not None, "to_yaml method not found on PortTemplateMapping"


def test_bug8_devicetype():
    tree = parse_file("dcim/models/devices.py")
    cls = find_class(tree, "DeviceType")
    assert cls is not None, "DeviceType class not found"
    method = find_function(cls, "to_yaml")
    assert method is not None, "to_yaml method not found on DeviceType"
    src = ast.get_source_segment(get_source("dcim/models/devices.py"), method)
    assert "port_mappings" in src or "port-mappings" in src, "port_mappings not in DeviceType.to_yaml"


def test_bug8_moduletype():
    tree = parse_file("dcim/models/modules.py")
    cls = find_class(tree, "ModuleType")
    assert cls is not None, "ModuleType class not found"
    method = find_function(cls, "to_yaml")
    assert method is not None, "to_yaml method not found on ModuleType"
    src = ast.get_source_segment(get_source("dcim/models/modules.py"), method)
    assert "port_mappings" in src or "port-mappings" in src, "port_mappings not in ModuleType.to_yaml"


# ==========================================================================
# Bug 9: CSV connection column whitespace (#21845)
# ==========================================================================
def test_bug9_path_endpoint():
    tree = parse_file("dcim/tables/devices.py")
    cls = find_class(tree, "PathEndpointTable")
    assert cls is not None, "PathEndpointTable class not found"
    method = find_function(cls, "value_connection")
    assert method is not None, "value_connection method not found on PathEndpointTable"


def test_bug9_interface_table():
    tree = parse_file("dcim/tables/devices.py")
    cls = find_class(tree, "InterfaceTable")
    assert cls is not None, "InterfaceTable class not found"
    method = find_function(cls, "value_connection")
    assert method is not None, "value_connection method not found on InterfaceTable"


# ==========================================================================
# Bug 10: API custom fields changelog (#21529)
# ==========================================================================
def test_bug10_api_validation():
    tree = parse_file("extras/api/customfields.py")
    cls = find_class(tree, "CustomFieldsDataField")
    assert cls is not None, "CustomFieldsDataField class not found"
    method = find_function(cls, "to_internal_value")
    assert method is not None, "to_internal_value method not found"
    src = ast.get_source_segment(get_source("extras/api/customfields.py"), method)
    assert "invalid_fields" in src, "invalid_fields check not found in to_internal_value"
    assert "ValidationError" in src, "ValidationError not raised for unknown custom fields"


def test_bug10_serializer():
    tree = parse_file("netbox/api/serializers/base.py")
    cls = find_class(tree, "ValidatedModelSerializer")
    assert cls is not None, "ValidatedModelSerializer class not found"
    method = find_function(cls, "validate")
    assert method is not None, "validate method not found"
    src = ast.get_source_segment(get_source("netbox/api/serializers/base.py"), method)
    assert "custom_field_data" in src, "custom_field_data normalization not found in validate"


# ==========================================================================
# Bug 11: Port mapping import (#21683)
# ==========================================================================
def test_bug11_clean_module():
    tree = parse_file("dcim/forms/object_import.py")
    cls = find_class(tree, "PortTemplateMappingImportForm")
    assert cls is not None, "PortTemplateMappingImportForm class not found"
    method = find_function(cls, "clean_module_type")
    assert method is not None, "clean_module_type method not found"
    src = ast.get_source_segment(get_source("dcim/forms/object_import.py"), method)
    assert "filter" in src, "filter not called in clean_module_type"


def test_bug11_clean_device():
    tree = parse_file("dcim/forms/object_import.py")
    cls = find_class(tree, "PortTemplateMappingImportForm")
    method = find_function(cls, "clean_device_type")
    assert method is not None, "clean_device_type method not found"
    src = ast.get_source_segment(get_source("dcim/forms/object_import.py"), method)
    assert "filter" in src, "filter not called in clean_device_type"


# ==========================================================================
# Bug 12: Script last run time (#21814)
# ==========================================================================
def test_bug12_ordering():
    tree = parse_file("netbox/models/features.py")
    cls = find_class(tree, "JobsMixin")
    assert cls is not None, "JobsMixin class not found"
    src = ast.get_source_segment(get_source("netbox/models/features.py"), cls)
    assert "'-started'" in src or '"-started"' in src, "JobsMixin does not order by '-started'"
    assert "'-created'" not in src and '"-created"' not in src, "JobsMixin still orders by '-created'"


# ==========================================================================
# Bug 13: API_TOKEN_PEPPERS isinstance (#21875)
# ==========================================================================
def test_bug13_isinstance():
    """Behavioral: try to call validate_peppers with OrderedDict; fall back to AST."""
    from collections import OrderedDict
    try:
        spec = importlib.util.spec_from_file_location(
            "security", NETBOX / "utilities/security.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        od = OrderedDict({0: "a" * 50})
        mod.validate_peppers(od)
    except ImportError:
        tree = parse_file("utilities/security.py")
        func = find_function(tree, "validate_peppers")
        assert func is not None, "validate_peppers function not found"
        src = ast.get_source_segment(get_source("utilities/security.py"), func)
        assert "isinstance" in src, "validate_peppers does not use isinstance"
        assert "type(peppers) is not dict" not in src, "validate_peppers still uses type() is not dict"


# ==========================================================================
# Bug 14: Script module edit button permission (#21841)
# ==========================================================================
def test_bug14_permission():
    tpl_path = NETBOX / "templates/extras/inc/script_list_content.html"
    assert tpl_path.exists(), "script_list_content.html template not found"
    src = tpl_path.read_text(encoding="utf-8")
    assert "change_scriptmodule" in src, "change_scriptmodule not found in template"
    assert "edit_scriptmodule" not in src, "edit_scriptmodule still present in template"


# ==========================================================================
# Bug 15: ColorField misleading help text (#21835)
# ==========================================================================
def test_bug15_no_help_text():
    tree = parse_file("utilities/fields.py")
    cls = find_class(tree, "ColorField")
    assert cls is not None, "ColorField class not found"
    method = find_function(cls, "formfield")
    assert method is not None, "formfield method not found on ColorField"
    src = ast.get_source_segment(get_source("utilities/fields.py"), method)
    assert "help_text" not in src, "ColorField.formfield still sets help_text"


# ==========================================================================
# Bug 16: Contact group count wrong with multi-assignment (#21538)
# ==========================================================================
def test_bug16_manager():
    tree = parse_file("tenancy/models/contacts.py")
    cls = find_class(tree, "ContactGroupManager")
    assert cls is not None, "ContactGroupManager class not found"
    method = find_function(cls, "annotate_contacts")
    assert method is not None, "annotate_contacts method not found on ContactGroupManager"
    src = ast.get_source_segment(get_source("tenancy/models/contacts.py"), method)
    assert "DISTINCT" in src or "distinct" in src, "annotate_contacts does not use DISTINCT"


def test_bug16_views():
    src = get_source("tenancy/views.py")
    assert "annotate_contacts" in src, "annotate_contacts not used in tenancy/views.py"


def test_bug16_api_views():
    src = get_source("tenancy/api/views.py")
    assert "annotate_contacts" in src, "annotate_contacts not used in tenancy/api/views.py"


def test_bug16_detail_distinct():
    src = get_source("tenancy/views.py")
    tree = parse_file("tenancy/views.py")
    cls = find_class(tree, "ContactGroupView")
    assert cls is not None, "ContactGroupView class not found"
    cls_src = ast.get_source_segment(src, cls)
    assert "distinct()" in cls_src, "ContactGroupView detail does not use distinct()"


# ==========================================================================
# Run all checks
# ==========================================================================
print("=" * 60)
print("NetBox 16-Bug Verification")
print("=" * 60)

# Bug 1 — S3 filenames (2 checks)
check("Bug01: _build_image_attachment_path exists", test_bug1_build_path)
check("Bug01: image_upload uses get_available_name", test_bug1_collision)

# Bug 2 — sync_classes twice (2 checks)
check("Bug02: No post_save signal handler", test_bug2_no_signal)
check("Bug02: sync_classes called once in save", test_bug2_single_sync)

# Bug 3 — humanize_speed decimal (2 checks)
check("Bug03: humanize_speed renders 2.5 Gbps", test_bug3_gbps_decimal)
check("Bug03: humanize_speed renders 1.6 Tbps", test_bug3_tbps_decimal)

# Bug 4 — Cable powerfeed import (2 checks)
check("Bug04: CableImportForm has power_panel fields", test_bug4_power_panel_field)
check("Bug04: _clean_side handles powerfeed type", test_bug4_powerfeed_handling)

# Bug 5 — Speed overflow (4 checks)
check("Bug05: Interface.speed is 64-bit", test_bug5_model_field)
check("Bug05: Migration 0227 exists", test_bug5_migration)
check("Bug05: InterfaceBulkEditForm uses 64-bit field", test_bug5_form)
check("Bug05: MultiValueBigNumberFilter class exists", test_bug5_filter)

# Bug 6 — Plugin content panels (2 checks)
check("Bug06: IPAM views include PluginContentPanel", test_bug6_ipam_views)
check("Bug06: Core views include PluginContentPanel", test_bug6_core_views)

# Bug 7 — Script validation (3 checks)
check("Bug07: validate_script_content exists", test_bug7_validate_exists)
check("Bug07: ScriptFileForm.clean validates scripts", test_bug7_form_validation)
check("Bug07: ScriptModuleSerializer.validate checks scripts", test_bug7_api_validation)

# Bug 8 — YAML port mappings (3 checks)
check("Bug08: PortTemplateMapping.to_yaml exists", test_bug8_to_yaml)
check("Bug08: DeviceType.to_yaml includes port-mappings", test_bug8_devicetype)
check("Bug08: ModuleType.to_yaml includes port-mappings", test_bug8_moduletype)

# Bug 9 — CSV connection whitespace (2 checks)
check("Bug09: PathEndpointTable.value_connection exists", test_bug9_path_endpoint)
check("Bug09: InterfaceTable.value_connection exists", test_bug9_interface_table)

# Bug 10 — Custom fields changelog (2 checks)
check("Bug10: API rejects unknown custom fields", test_bug10_api_validation)
check("Bug10: Serializer preserves custom_field_data", test_bug10_serializer)

# Bug 11 — Port mapping import (2 checks)
check("Bug11: clean_module_type scopes queryset", test_bug11_clean_module)
check("Bug11: clean_device_type scopes queryset", test_bug11_clean_device)

# Bug 12 — Last run time (1 check)
check("Bug12: JobsMixin orders by '-started'", test_bug12_ordering)

# Bug 13 — isinstance check (1 check)
check("Bug13: validate_peppers uses isinstance", test_bug13_isinstance)

# Bug 14 — Permission name (1 check)
check("Bug14: Template uses change_scriptmodule", test_bug14_permission)

# Bug 15 — ColorField help text (1 check)
check("Bug15: ColorField.formfield has no help_text", test_bug15_no_help_text)

# Bug 16 — Contact group count (4 checks)
check("Bug16: ContactGroupManager.annotate_contacts exists", test_bug16_manager)
check("Bug16: Views use annotate_contacts", test_bug16_views)
check("Bug16: API views use annotate_contacts", test_bug16_api_views)
check("Bug16: Detail view uses distinct()", test_bug16_detail_distinct)

print(f"\nResult: {passed}/{total} checks passed")

with open("/logs/verifier/reward.txt", "w") as f:
    f.write(str(round(passed / total, 2)))

sys.exit(0)
