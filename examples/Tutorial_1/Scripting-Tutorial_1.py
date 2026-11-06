"""
RSSeismic scripting tutorial 1 — simple GQ/H profile and compute.

Run from the repo root (RSSeismic scripting server on port 60058):

    python examples/Tutorial_1/Scripting-Tutorial_1.py
"""

import math
import os

from rsseismic import RSSeismicApplication, UnitSystem

# =============================================================================
# Step 1 — Configuration
# =============================================================================
_TUTORIAL_ROOT = os.path.dirname(os.path.abspath(__file__))
_OUTPUT_DIR = os.path.join(_TUTORIAL_ROOT, "projects")
OUTPUT_PROJECT = os.path.join(_OUTPUT_DIR, "tutorial_1_simple_profile.rsseismicfile")
PROFILE_NAME = "Profile 1"

CHICHI_MOTION_NAME = "ChiChi"

N_LAYERS = 5
THICKNESS = 5.0     # m
UNIT_WEIGHT = 20.0  # kN/m³
VS = 250.0          # m/s
K0 = 0.46
PI_VALUE = 0.0      # plasticity index (%)
PHI_DEG = 35.0      # friction angle (degrees)

# =============================================================================
# Step 2 — Connect and create a blank project
# =============================================================================
SCRIPTING_PORT = 60058
app = RSSeismicApplication(port=SCRIPTING_PORT)
app.ping()
model = app.newProject()

# =============================================================================
# Step 3 — Project settings
# =============================================================================

model.ProjectSettings.changeUnitSystem(UnitSystem.Metric)
model.ProjectSettings.Data.setBoolValue("automaticProfileGeneration", False)
model.ProjectSettings.Data.setEnumValue("analysisMode", "Nonlinear")
model.ProjectSettings.Data.setEnumValue("defaultSoilModel", "GQ_H")
model.ProjectSettings.Data.setEnumValue("hystereticFormulation", "NonMasing")

# =============================================================================
# Step 4 — Build five GQ/H layers on Profile 1
# =============================================================================
# A new project already has "Profile 1" with one default soil layer.
# Add four more layers, then set properties on all five.

model.Profiles.setActiveProfile(PROFILE_NAME)

layers = model.Profiles.listActiveSoilLayers()
model.SoilLayers.appendLayers(N_LAYERS - len(layers))

for i, summary in enumerate(model.Profiles.listActiveSoilLayers()):
    layer = model.Profiles.getSoilLayer(summary.layerID)

    z_mid = i * THICKNESS + THICKNESS / 2.0
    sigma_v = UNIT_WEIGHT * z_mid
    tau_max = sigma_v * math.tan(math.radians(PHI_DEG))

    layer.setSoilModel("GQ_H")
    layer.setThickness(THICKNESS)
    layer.setUnitWeight(UNIT_WEIGHT)
    layer.Data.setDoubleProperty("ShearWaveVelocity", VS)
    layer.Data.setDoubleProperty("ShearStrength", tau_max)

    ref = layer.ReferenceCurve
    ref.setSoilType("Sand")
    ref.setCurveModel("Darendeli_2001")
    ref.Data.setDoubleProperty("Ko", K0)
    ref.Data.setDoubleProperty("PI", PI_VALUE)
    ref.generateReferenceCurve()
    layer.Curve.runCurveFit("MRDF_UIUC")

# =============================================================================
# Step 5 — Select ChiChi motion
# =============================================================================

model.Motions.refreshMotionsList()
model.Motions.setMotionSelection([CHICHI_MOTION_NAME], selectOnlyListed=True)

# =============================================================================
# Step 6 — Save and compute
# =============================================================================

os.makedirs(os.path.dirname(OUTPUT_PROJECT), exist_ok=True)
model.saveAs(OUTPUT_PROJECT)
model.runCompute()

# =============================================================================
# Step 7 — Result path (on disk, next to the project file)
# =============================================================================

project_stem = os.path.splitext(os.path.basename(OUTPUT_PROJECT))[0]
db3_path = os.path.join(
    os.path.dirname(OUTPUT_PROJECT),
    project_stem,
    PROFILE_NAME,
    f"Motion_{CHICHI_MOTION_NAME}",
    "deepsoilout.db3",
)
print(db3_path)

model.close(saveProject=False)
app.close()
