"""
tests/test_fusion_api_mock.py
---------------------------------------------------------------------------
Comprehensive Mock & Integration Test Suite for Autodesk Fusion 360 API calls.

Validates that all Autodesk Fusion API interactions in fusion_conveyor_generator.py
(sketches, extrusions, parametric user parameters, rectangular patterns,
feature suppression, bounding box validation, timeline grouping, and STEP export)
invoke the expected Autodesk Fusion API interfaces with valid signatures and parameters.
"""

import math
import os
import sys
import tempfile
import unittest
from typing import Any, Dict, List, Optional


# ===========================================================================
# 1. AUTODESK FUSION API MOCK FRAMEWORK (adsk.core & adsk.fusion)
# ===========================================================================

class MockValueInput:
    def __init__(self, string_value: str = "", real_value: float = 0.0):
        self.stringValue = string_value
        self.realValue = real_value

    @staticmethod
    def createByString(expr: str):
        return MockValueInput(string_value=expr)

    @staticmethod
    def createByReal(val: float):
        return MockValueInput(real_value=val)


class MockPoint3D:
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    @staticmethod
    def create(x: float = 0.0, y: float = 0.0, z: float = 0.0):
        return MockPoint3D(x, y, z)


class MockMatrix3D:
    @staticmethod
    def create():
        return MockMatrix3D()


class MockObjectCollection:
    def __init__(self):
        self._items: List[Any] = []

    @staticmethod
    def create():
        return MockObjectCollection()

    def add(self, item: Any):
        self._items.append(item)

    @property
    def count(self) -> int:
        return len(self._items)

    def item(self, index: int) -> Any:
        return self._items[index]

    def __iter__(self):
        return iter(self._items)


class MockUserParameter:
    def __init__(self, name: str, expression: str, unit: str, comment: str, user_params: "MockUserParameters"):
        self.name = name
        self._expression = expression
        self.unit = unit
        self.comment = comment
        self._user_params = user_params

    @property
    def expression(self) -> str:
        return self._expression

    @expression.setter
    def expression(self, val: str):
        self._expression = str(val)

    @property
    def value(self) -> float:
        """Evaluate numeric value in database units (cm for length, unitless for count)."""
        expr = self._expression.strip()
        expr_no_unit = expr.replace("mm", "").replace("cm", "").strip()
        try:
            val = float(expr_no_unit)
            if self.unit == "mm":
                return val / 10.0  # Fusion DB unit is cm
            return val
        except ValueError:
            pass

        # Formula evaluation for count parameters
        up = self._user_params
        if self.name == "RollerCount":
            length_mm = up._get_val_mm("ConvLength")
            dia = up._get_val_mm("RollerDia")
            margin = dia / 2.0 + 10.0
            p = up._get_val_mm("RollerSpacing")
            return float(math.floor((length_mm - 2 * margin) / p) + 1)
        elif self.name == "LegCount":
            length_mm = up._get_val_mm("ConvLength")
            s = up._get_val_mm("LegSpacing")
            leg_side = 40.0
            return float(math.floor((length_mm - leg_side) / s) + 1)
        return 1.0


class MockUserParameters:
    def __init__(self):
        self._params: Dict[str, MockUserParameter] = {}

    def itemByName(self, name: str) -> Optional[MockUserParameter]:
        return self._params.get(name)

    def add(self, name: str, value_input: MockValueInput, unit: str, comment: str = "") -> MockUserParameter:
        p = MockUserParameter(name, value_input.stringValue, unit, comment, self)
        self._params[name] = p
        return p

    @property
    def count(self) -> int:
        return len(self._params)

    def _get_val_mm(self, name: str) -> float:
        p = self.itemByName(name)
        if not p:
            return 0.0
        val_str = p.expression.replace("mm", "").replace("cm", "").strip()
        try:
            return float(val_str)
        except ValueError:
            return 0.0


class MockSketchPoint:
    def __init__(self, pt: MockPoint3D):
        self.geometry = pt


class MockSketchLine:
    def __init__(self, start: MockPoint3D, end: MockPoint3D):
        self.startSketchPoint = MockSketchPoint(start)
        self.endSketchPoint = MockSketchPoint(end)


class MockSketchLines:
    def __init__(self):
        self._lines: List[MockSketchLine] = []

    def addTwoPointRectangle(self, p1: MockPoint3D, p2: MockPoint3D):
        coll = MockObjectCollection()
        l1 = MockSketchLine(p1, MockPoint3D(p2.x, p1.y, p1.z))
        l2 = MockSketchLine(MockPoint3D(p2.x, p1.y, p1.z), p2)
        l3 = MockSketchLine(p2, MockPoint3D(p1.x, p2.y, p2.z))
        l4 = MockSketchLine(MockPoint3D(p1.x, p2.y, p2.z), p1)
        for line in [l1, l2, l3, l4]:
            coll.add(line)
            self._lines.append(line)
        return coll


class MockSketchCircle:
    def __init__(self, center: MockPoint3D, radius: float):
        self.centerSketchPoint = MockSketchPoint(center)
        self.radius = radius


class MockSketchCircles:
    def addByCenterRadius(self, center: MockPoint3D, radius: float):
        return MockSketchCircle(center, radius)


class MockSketchCurves:
    def __init__(self):
        self.sketchLines = MockSketchLines()
        self.sketchCircles = MockSketchCircles()


class MockDimensionParameter:
    def __init__(self):
        self.expression = ""


class MockSketchDimension:
    def __init__(self):
        self.parameter = MockDimensionParameter()


class MockSketchDimensions:
    def __init__(self):
        self.dimensions: List[MockSketchDimension] = []

    def addDistanceDimension(self, pt1, pt2, orientation, text_pos):
        d = MockSketchDimension()
        self.dimensions.append(d)
        return d

    def addDiameterDimension(self, circle, text_pos):
        d = MockSketchDimension()
        self.dimensions.append(d)
        return d


class MockProfile:
    pass


class MockProfiles:
    def __init__(self, count: int = 2):
        self._count = count
        self._items = [MockProfile() for _ in range(count)]

    @property
    def count(self) -> int:
        return self._count

    def item(self, idx: int):
        return self._items[idx]


class MockSketch:
    def __init__(self, name: str = "", profile_count: int = 2):
        self.name = name
        self.sketchCurves = MockSketchCurves()
        self.sketchDimensions = MockSketchDimensions()
        self.originPoint = MockSketchPoint(MockPoint3D(0, 0, 0))
        self.profiles = MockProfiles(profile_count)


class MockSketches:
    def __init__(self):
        self.sketches: List[MockSketch] = []

    def add(self, plane):
        sk_name = ""
        # Determine expected profile count based on sketch type
        profile_count = 2
        sk = MockSketch(sk_name, profile_count=profile_count)
        self.sketches.append(sk)
        return sk


class MockBRepBody:
    def __init__(self, name: str = ""):
        self.name = name


class MockExtrudeFeature:
    def __init__(self, name: str = ""):
        self.name = name
        self.isSuppressed = False
        self.bodies = MockObjectCollection()
        self.bodies.add(MockBRepBody(f"Body_{name}"))


class MockExtrudeInput:
    def __init__(self, profiles, operation):
        self.profiles = profiles
        self.operation = operation
        self.extent = None

    def setOneSideExtent(self, extent_def, direction):
        self.extent = extent_def


class MockExtrudeFeatures:
    def __init__(self, design: Optional["MockDesign"] = None):
        self.features: List[MockExtrudeFeature] = []
        self._design = design

    def createInput(self, profiles, operation):
        return MockExtrudeInput(profiles, operation)

    def add(self, ext_input: MockExtrudeInput):
        feat = MockExtrudeFeature("Feature_Extrude")
        self.features.append(feat)
        if self._design and hasattr(self._design, "timeline"):
            self._design.timeline.count += 1
        return feat


class MockPatternFeature:
    def __init__(self, name: str = ""):
        self.name = name
        self.computeType = None


class MockPatternInput:
    def __init__(self, entities, axis, count_input, spacing_input, dist_type):
        self.entities = entities
        self.axis = axis
        self.count_input = count_input
        self.spacing_input = spacing_input
        self.dist_type = dist_type


class MockRectangularPatternFeatures:
    def __init__(self, design: Optional["MockDesign"] = None):
        self.patterns: List[MockPatternFeature] = []
        self._design = design

    def createInput(self, entities, axis, count_input, spacing_input, dist_type):
        return MockPatternInput(entities, axis, count_input, spacing_input, dist_type)

    def add(self, pattern_input: MockPatternInput):
        p = MockPatternFeature("Pattern")
        self.patterns.append(p)
        if self._design and hasattr(self._design, "timeline"):
            self._design.timeline.count += 1
        return p


class MockConstructionPlane:
    def __init__(self, name: str = ""):
        self.name = name


class MockConstructionPlaneInput:
    def setByOffset(self, planar_entity, offset_val):
        self.planar_entity = planar_entity
        self.offset_val = offset_val


class MockConstructionPlanes:
    def createInput(self):
        return MockConstructionPlaneInput()

    def add(self, plane_input):
        return MockConstructionPlane("Plane")


class MockBoundingBox3D:
    def __init__(self, comp: "MockComponent"):
        self.comp = comp

    @property
    def minPoint(self) -> MockPoint3D:
        return MockPoint3D(0.0, 0.0, 0.0)

    @property
    def maxPoint(self) -> MockPoint3D:
        # Fusion bounding box is in cm (DB units). 1 cm = 10 mm.
        up = self.comp.design.userParameters
        l_mm = up._get_val_mm("ConvLength") or 1400.0
        w_mm = up._get_val_mm("ConvWidth") or 450.0
        h_mm = up._get_val_mm("FrameHeight") or 700.0
        d_mm = up._get_val_mm("RollerDia") or 60.0
        g_mm = up._get_val_mm("GuardHeight") or 75.0

        ext_guards = getattr(self.comp, "_ext_guards", None)
        guards_suppressed = ext_guards.isSuppressed if ext_guards else False

        roller_top = h_mm + d_mm / 2.0
        if not guards_suppressed:
            total_h = max(roller_top, h_mm + g_mm)
        else:
            total_h = roller_top

        return MockPoint3D(l_mm / 10.0, w_mm / 10.0, total_h / 10.0)


class MockComponent:
    def __init__(self, design: "MockDesign", name: str = ""):
        self.design = design
        self.name = name
        self.sketches = MockSketches()
        self.constructionPlanes = MockConstructionPlanes()
        self.features = type("MockFeatures", (), {
            "extrudeFeatures": MockExtrudeFeatures(design),
            "rectangularPatternFeatures": MockRectangularPatternFeatures(design),
        })()
        self.xYConstructionPlane = MockConstructionPlane("XY")
        self.xZConstructionPlane = MockConstructionPlane("XZ")
        self.xConstructionAxis = "X_Axis"
        self._ext_guards: Optional[MockExtrudeFeature] = None

    @property
    def boundingBox(self) -> MockBoundingBox3D:
        return MockBoundingBox3D(self)


class MockOccurrence:
    def __init__(self, comp: MockComponent, name: str = ""):
        self.component = comp
        self.name = name

    def deleteMe(self):
        pass


class MockOccurrences:
    def __init__(self, design: "MockDesign"):
        self.design = design
        self._list: List[MockOccurrence] = []

    def __iter__(self):
        return iter(self._list)

    def addNewComponent(self, matrix: MockMatrix3D) -> MockOccurrence:
        comp = MockComponent(self.design, "ParametricConveyor_Assembly")
        occ = MockOccurrence(comp, "ParametricConveyor_Assembly")
        self._list.append(occ)
        return occ


class MockSTEPExportOptions:
    def __init__(self, filename: str, component: MockComponent):
        self.filename = filename
        self.component = component


class MockExportManager:
    def __init__(self):
        self.exported_files: List[str] = []

    def createSTEPExportOptions(self, filename: str, component: MockComponent):
        return MockSTEPExportOptions(filename, component)

    def execute(self, options: MockSTEPExportOptions):
        self.exported_files.append(options.filename)
        # Write dummy file so downstream os.path.exists checks succeed
        with open(options.filename, "w", encoding="utf-8") as f:
            f.write("ISO-10303-21; /* Mock STEP CAD Export */\n")


class MockTimelineGroups:
    def __init__(self):
        self.groups: List[tuple] = []

    def add(self, start_idx: int, end_idx: int):
        self.groups.append((start_idx, end_idx))


class MockTimeline:
    def __init__(self):
        self.count = 10
        self.timelineGroups = MockTimelineGroups()


class MockDesign:
    def __init__(self):
        self.userParameters = MockUserParameters()
        self.rootComponent = MockComponent(self, "RootComponent")
        self.rootComponent.occurrences = MockOccurrences(self)
        self.exportManager = MockExportManager()
        self.timeline = MockTimeline()
        self.compute_all_calls = 0

    def computeAll(self):
        self.compute_all_calls += 1


class MockApplication:
    @staticmethod
    def get():
        return MockApplication()

    def log(self, msg: str):
        pass


# Assemble adsk mock module structure
class MockAdskCore:
    Application = MockApplication
    Point3D = MockPoint3D
    Matrix3D = MockMatrix3D
    ValueInput = MockValueInput
    ObjectCollection = MockObjectCollection

    class CustomEventHandler:
        pass

    class CustomEventArgs:
        pass


class MockDimensionOrientations:
    AlignedDimensionOrientation = "Aligned"
    VerticalDimensionOrientation = "Vertical"
    HorizontalDimensionOrientation = "Horizontal"


class MockFeatureOperations:
    NewBodyFeatureOperation = "NewBody"


class MockPatternDistanceType:
    SpacingPatternDistanceType = "Spacing"


class MockDistanceExtentDefinition:
    @staticmethod
    def create(value_input):
        return value_input


class MockExtentDirections:
    PositiveExtentDirection = "Positive"


class MockAdskFusion:
    Design = MockDesign
    DimensionOrientations = MockDimensionOrientations
    FeatureOperations = MockFeatureOperations
    PatternDistanceType = MockPatternDistanceType
    DistanceExtentDefinition = MockDistanceExtentDefinition
    ExtentDirections = MockExtentDirections


class MockAdsk:
    core = MockAdskCore
    fusion = MockAdskFusion


# ===========================================================================
# 2. INTEGRATION TESTS FOR AUTODESK FUSION API SCRIPT
# ===========================================================================

class AutodeskFusionApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        """Inject adsk mock into sys.modules and fusion_conveyor_generator."""
        self.mock_adsk = MockAdsk()
        sys.modules["adsk"] = self.mock_adsk
        sys.modules["adsk.core"] = MockAdskCore
        sys.modules["adsk.fusion"] = MockAdskFusion

        import fusion_conveyor_generator as fcg
        self.fcg = fcg
        fcg.adsk = self.mock_adsk

        self.design = MockDesign()

    def test_create_user_parameters_creates_all_required_specs(self):
        """Verify all base dimensions, structural constants, and formulas are added."""
        demo = self.fcg.demo_configurations()["C2_medium_with_guards"]
        self.fcg.create_user_parameters(self.design, demo)

        up = self.design.userParameters
        expected_params = [
            "ConvLength", "ConvWidth", "FrameHeight", "RollerDia",
            "RollerSpacing", "LegSpacing", "GuardHeight",
            "RailW", "RailH", "LegSide", "RollerClearance", "GuardThick", "RollerMargin",
            "RollerCount", "LegCount"
        ]

        for p_name in expected_params:
            p = up.itemByName(p_name)
            self.assertIsNotNone(p, f"Parameter '{p_name}' was not created in UserParameters")
            self.assertTrue(len(p.expression) > 0, f"Parameter '{p_name}' has empty expression")

        # Check values
        self.assertEqual(up.itemByName("ConvLength").expression, f"{demo.length_mm} mm")
        self.assertEqual(up.itemByName("ConvWidth").expression, f"{demo.width_mm} mm")
        self.assertEqual(up.itemByName("FrameHeight").expression, f"{demo.height_mm} mm")
        self.assertIn("floor", up.itemByName("RollerCount").expression)
        self.assertIn("floor", up.itemByName("LegCount").expression)

    def test_build_parametric_conveyor_model_constructs_feature_tree(self):
        """Verify build_parametric_conveyor creates sketches, extrudes, patterns, and groups."""
        demo = self.fcg.demo_configurations()["C2_medium_with_guards"]
        self.fcg.create_user_parameters(self.design, demo)
        refs = self.fcg.build_parametric_conveyor_model(self.design)

        self.assertIn("component", refs)
        self.assertIn("ext_guards", refs)
        self.assertIn("pattern_rollers", refs)
        self.assertIn("pattern_legs", refs)

        comp = refs["component"]
        self.assertEqual(comp.name, "ParametricConveyor_Assembly")
        # 4 Sketches: SideRails, MasterRoller, LegPair, SideGuards
        self.assertEqual(len(comp.sketches.sketches), 4)
        # 4 Extrusions: SideRails, MasterRoller, MasterLegs, SideGuards
        self.assertEqual(len(comp.features.extrudeFeatures.features), 4)
        # 2 Rectangular patterns: Rollers, Legs
        self.assertEqual(len(comp.features.rectangularPatternFeatures.patterns), 2)
        # Timeline group created
        self.assertGreaterEqual(len(self.design.timeline.timelineGroups.groups), 1)

    def test_update_model_parameters_in_place(self):
        """Verify updating model parameters re-sets expressions and toggles suppression."""
        c2 = self.fcg.demo_configurations()["C2_medium_with_guards"]
        c1 = self.fcg.demo_configurations()["C1_compact_no_guards"]

        self.fcg.create_user_parameters(self.design, c2)
        refs = self.fcg.build_parametric_conveyor_model(self.design)
        refs["component"]._ext_guards = refs["ext_guards"]

        # Update to C1 (no side guards)
        self.fcg.update_model_parameters(self.design, refs, c1)

        up = self.design.userParameters
        self.assertEqual(up.itemByName("ConvLength").expression, f"{c1.length_mm} mm")
        self.assertEqual(up.itemByName("ConvWidth").expression, f"{c1.width_mm} mm")
        self.assertTrue(refs["ext_guards"].isSuppressed, "Side guards should be suppressed for C1")
        self.assertGreater(self.design.compute_all_calls, 0)

    def test_validate_cad_model_against_tolerances(self):
        """Verify bounding box calculation and tolerance verification against CAD model."""
        c2 = self.fcg.demo_configurations()["C2_medium_with_guards"]
        self.fcg.create_user_parameters(self.design, c2)
        refs = self.fcg.build_parametric_conveyor_model(self.design)
        refs["component"]._ext_guards = refs["ext_guards"]

        checks = self.fcg.validate_cad_model(self.design, refs["component"], c2, refs)
        self.assertTrue(len(checks) >= 5)
        for label, passed, detail in checks:
            self.assertTrue(passed, f"CAD check failed: {label} ({detail})")

    def test_export_step_file_executes_api(self):
        """Verify STEP export invokes exportManager and writes output."""
        c2 = self.fcg.demo_configurations()["C2_medium_with_guards"]
        self.fcg.create_user_parameters(self.design, c2)
        refs = self.fcg.build_parametric_conveyor_model(self.design)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = self.fcg.export_step_file(self.design, refs["component"], "Test_C2", tmpdir)
            self.assertTrue(os.path.exists(out_path))
            self.assertEqual(len(self.design.exportManager.exported_files), 1)

    def test_run_batch_demonstration_end_to_end(self):
        """Verify complete batch runner builds all 3 configurations with zero failures."""
        demos = self.fcg.demo_configurations()
        first_cfg = list(demos.values())[0]

        self.fcg.create_user_parameters(self.design, first_cfg)
        refs = self.fcg.build_parametric_conveyor_model(self.design)
        refs["component"]._ext_guards = refs["ext_guards"]

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, log_path = self.fcg.run_batch_demonstration(self.design, refs, tmpdir)

            self.assertTrue(os.path.exists(report_path))
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("--- Configuration: C1_compact_no_guards ---", content)
            self.assertIn("--- Configuration: C2_medium_with_guards ---", content)
            self.assertIn("--- Configuration: C3_long_with_guards ---", content)
            self.assertNotIn("[FAIL]", content)
            self.assertIn("[PASS]", content)

    def test_build_falls_back_to_root_in_part_docs(self):
        """Part-design docs (addNewComponent raises) build the same tree in root."""
        demo = self.fcg.demo_configurations()["C2_medium_with_guards"]
        self.fcg.create_user_parameters(self.design, demo)

        real_occs = self.design.rootComponent.occurrences

        class FailingOccurrences:
            def __iter__(self):
                return iter([])

            def addNewComponent(self, _matrix):
                raise RuntimeError("Part Design documents can only contain one component")

        self.design.rootComponent.occurrences = FailingOccurrences()
        try:
            refs = self.fcg.build_parametric_conveyor_model(self.design)
        finally:
            self.design.rootComponent.occurrences = real_occs

        self.assertIsNone(refs["occurrence"])
        self.assertIs(refs["component"], self.design.rootComponent)
        self.assertEqual(len(refs["component"].sketches.sketches), 4)
        self.assertEqual(len(refs["component"].features.extrudeFeatures.features), 4)
        self.assertEqual(len(refs["component"].features.rectangularPatternFeatures.patterns), 2)


if __name__ == "__main__":
    unittest.main()
