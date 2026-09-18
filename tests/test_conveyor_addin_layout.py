"""Offline layout tests for the tabbed dialog (no Fusion needed).

Minimal-risk guard: tabbed redesign must keep all input IDs, 440px width,
strict validation contract, and a flat fallback for old builds.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "conveyor_addin"))

import conveyor_addin as addin  # noqa: E402


class _FakeListItems:
    def __init__(self):
        self.names = []

    def add(self, name, selected=False):
        self.names.append(name)
        return name

    @property
    def count(self):
        return len(self.names)


class _FakeBase:
    def __init__(self, ident):
        self.id = ident
        self.isVisible = True
        self.isEnabled = True
        self.isExpanded = True
        self.tooltip = ""


class _FakeDropDown(_FakeBase):
    def __init__(self, ident):
        super().__init__(ident)
        self.listItems = _FakeListItems()


class _FakeValue(_FakeBase):
    def __init__(self, ident, expression=""):
        super().__init__(ident)
        self.expression = expression


class _FakeBool(_FakeBase):
    def __init__(self, ident, value=False):
        super().__init__(ident)
        self.value = value


class _FakeTextBox(_FakeBase):
    def __init__(self, ident, text="", num_rows=1):
        super().__init__(ident)
        self.text = text
        self.numRows = num_rows


class _FakeGroup(_FakeBase):
    def __init__(self, ident):
        super().__init__(ident)
        self.children = FakeInputs()


class _FakeTab(_FakeBase):
    def __init__(self, ident):
        super().__init__(ident)
        self.children = FakeInputs()

    def activate(self):
        return True


class FakeInputs:
    """Mimics adsk.core.CommandInputs (recursive itemById)."""

    def __init__(self, with_tabs=True, with_separators=True):
        self._store = {}
        self.with_tabs = with_tabs
        self.with_separators = with_separators
        self.separators = []

    def _reg(self, obj):
        self._store[obj.id] = obj
        return obj

    def addTabCommandInput(self, ident, name, resourceFolder=""):
        if not self.with_tabs:
            raise RuntimeError("tabs unsupported")
        return self._reg(_FakeTab(ident))

    def addSeparatorCommandInput(self, ident):
        if not self.with_separators:
            raise RuntimeError("separators unsupported")
        self.separators.append(ident)
        sep = _FakeBase(ident)
        return self._reg(sep)

    def addGroupCommandInput(self, ident, name):
        return self._reg(_FakeGroup(ident))

    def addDropDownCommandInput(self, ident, name, style):
        return self._reg(_FakeDropDown(ident))

    def addValueInput(self, ident, name, unit, value_input):
        expr = getattr(value_input, "expr", "")
        return self._reg(_FakeValue(ident, expr))

    def addStringValueInput(self, ident, name, value):
        obj = _FakeBase(ident)
        obj.value = value
        return self._reg(obj)

    def addBoolValueInput(self, ident, name, checkbox, resource, value):
        return self._reg(_FakeBool(ident, value))

    def addTextBoxCommandInput(self, ident, name, text, num_rows, readonly):
        return self._reg(_FakeTextBox(ident, text, num_rows))

    def itemById(self, ident):
        if ident in self._store:
            return self._store[ident]
        for obj in self._store.values():
            children = getattr(obj, "children", None)
            if children is not None:
                found = children.itemById(ident)
                if found is not None:
                    return found
        return None


class _FakeValueInputFactory:
    def __init__(self, expr):
        self.expr = expr


class _FakeCore:
    class DropDownStyles:
        LabeledIconDropDownStyle = 0

    class ValueInput:
        @staticmethod
        def createByString(expr):
            return _FakeValueInputFactory(expr)


class _FakeAdsk:
    core = _FakeCore()


REQUIRED_IDS = [
    addin.MODULE_TYPE_ID, addin.PRESET_ID, addin.DUTY_CLASS_ID,
    addin.TARGET_LOAD_ID, addin.AUTO_OPTIMIZE_ID, addin.CROSS_BRACE_ID,
    addin.GUARDS_ID, addin.PREVIEW_ID, addin.LOG_ID, addin.EXPORT_BTN_ID,
    "in_length", "in_width", "in_height", "in_dia", "in_pitch",
    "in_leg", "in_guard", "in_radius", "in_angle",
]


class DialogLayoutTests(unittest.TestCase):
    def _build(self, with_tabs=True):
        inputs = FakeInputs(with_tabs=with_tabs)
        defaults = addin.dialog_defaults()
        presets = addin.load_presets()
        refs = addin.build_dialog_layout(inputs, defaults, presets, adsk_mod=_FakeAdsk())
        return inputs, refs

    def test_tabbed_layout_keeps_all_ids(self):
        inputs, refs = self._build(with_tabs=True)
        self.assertTrue(refs["tabbed"])
        self.assertEqual(len(refs["tabs"]), 4)
        for ident in REQUIRED_IDS:
            self.assertIsNotNone(inputs.itemById(ident), f"missing {ident}")

    def test_tab_ids_and_width_contract(self):
        self.assertEqual(addin.DIALOG_MIN_WIDTH, 440)
        self.assertEqual(addin.TAB_SETUP_ID, "tab_setup")
        self.assertEqual(addin.TAB_DIMS_ID, "tab_dimensions")
        self.assertEqual(addin.TAB_CAPACITY_ID, "tab_capacity")
        self.assertEqual(addin.TAB_PREVIEW_ID, "tab_preview")

    def test_straight_visible_curve_hidden_initially(self):
        inputs, _ = self._build(with_tabs=True)
        self.assertTrue(inputs.itemById("group_straight").isVisible)
        self.assertFalse(inputs.itemById("group_curved").isVisible)

    def test_separators_give_spacing(self):
        inputs, _ = self._build(with_tabs=True)
        # separators live inside tab children; count recursively
        total = list(inputs.separators)
        for obj in list(inputs._store.values()):
            children = getattr(obj, "children", None)
            if children is not None:
                total.extend(children.separators)
        self.assertGreaterEqual(len(total), 3)

    def test_preview_log_rows_reclaim_space(self):
        inputs, _ = self._build(with_tabs=True)
        self.assertEqual(inputs.itemById(addin.PREVIEW_ID).numRows, addin.PREVIEW_ROWS)
        self.assertEqual(inputs.itemById(addin.LOG_ID).numRows, addin.LOG_ROWS)
        self.assertLessEqual(inputs.itemById(addin.LOG_ID).numRows, 3)

    def test_flat_fallback_keeps_all_ids(self):
        inputs, refs = self._build(with_tabs=False)
        self.assertFalse(refs["tabbed"])
        for ident in REQUIRED_IDS:
            self.assertIsNotNone(inputs.itemById(ident), f"fallback missing {ident}")


if __name__ == "__main__":
    unittest.main()
