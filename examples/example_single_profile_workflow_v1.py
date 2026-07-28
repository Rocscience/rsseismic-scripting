"""
GQ/H nonlinear analysis — 5-layer dry sand profile, Darendeli curves, MRDF fitting, ChiChi motion.
All property name strings verified against DeepSoilFile/SoilLayer.cs and ProjectSettings.cs.
"""

from __future__ import annotations
import math, os
from rsseismic import RSSeismicApplication, logger
from rsseismic.enums import FittingProcedureModel

# ── Configuration ──────────────────────────────────────────────────────────
OUTPUT_PROJECT     = r"C:\Users\DylanCentella\source\repos\RSSeismicScripting\tests\resources\test_profile.rsseismicfile"
SCRIPTING_PORT     = 60058
CHICHI_MOTION_DIR  = r"C:\Program Files\Rocscience\RSSeismic\Resources\InputMotions"
CHICHI_MOTION_NAME = "ChiChi"   # verify with model.Motions.listMotions() if unsure
PROFILE_NAME       = "Profile 1"

# Layer properties (metric: m, kN/m³, kPa)
N_LAYERS     = 5
THICKNESS    = 5.0    # m
UNIT_WEIGHT  = 20.0   # kN/m³
VS           = 250.0  # m/s  — set via "ShearWaveVelocity"; Gmax computed automatically
K0           = 0.46   # lateral earth pressure coefficient — key is "Ko" (letter o, not zero)
PI           = 0.0    # plasticity index
PHI_DEG      = 35.0   # friction angle (degrees) — used to compute ShearStrength per layer

def shear_strength_kPa(layer_index_0: int) -> float:
    """τ_max = σ'v_mid · tan(φ')   [dry profile, c'=0, σ'v = total stress]"""
    z_mid = layer_index_0 * THICKNESS + THICKNESS / 2.0
    sigma_v_eff = UNIT_WEIGHT * z_mid          # kPa
    return sigma_v_eff * math.tan(math.radians(PHI_DEG))

# ── Main ───────────────────────────────────────────────────────────────────
def main() -> None:
    app = RSSeismicApplication(port=SCRIPTING_PORT)
    app.ping()
    model = app.newProject()

    try:
        # 1. Analysis mode — confirmed enum value: "Nonlinear" (not "NonLinear")
        model.ProjectSettings.Data.setEnumValue("analysisMode", "Nonlinear")
        model.ProjectSettings.Data.setEnumValue("hystereticFormulation", "NonMasing") 

        # 2. Activate target profile
        model.Profiles.setActiveProfile(PROFILE_NAME)

        # 3. Remove any existing layers, add 5 fresh ones
        # Get the existing layers BEFORE adding new ones
        existing = model.Profiles.listActiveSoilLayers()

        # Add the 5 new layers first (now there's always more than one layer)
        result = model.SoilLayers.appendLayers(N_LAYERS)
        layer_ids = list(result.layerIDs)

        # Now it's safe to delete the originals
        for s in existing:
            model.SoilLayers.deleteLayer(s.layerID)

        # 4. Configure each layer
        for i, lid in enumerate(layer_ids):
            layer = model.Profiles.getSoilLayer(lid)
            tau_max = shear_strength_kPa(i)

            # Basic properties — all confirmed names from SoilLayer.cs
            layer.setThickness(THICKNESS)
            layer.setUnitWeight(UNIT_WEIGHT)
            layer.setSoilModel("GQ_H")                              # eSoilModel.GQ_H
            layer.Data.setDoubleProperty("ShearWaveVelocity", VS)   # Gmax computed automatically
            layer.Data.setDoubleProperty("ShearStrength", tau_max)  # τ_max in kPa

            # 5. Darendeli reference curve
            ref = layer.ReferenceCurve
            ref.setSoilType("Sand")                    # eSoilType.Sand (PI=0 → sandy)
            ref.setCurveModel("Darendeli_2001")        # eCurveModel.Darendeli_2001
            ref.Data.setDoubleProperty("Ko", K0)       # "Ko" — letter 'o', NOT the number '0'
            ref.Data.setDoubleProperty("PI", PI)       # "PI" confirmed in ReferenceCurve.cs
            # OCR, N, Frequency, etc. left at their project defaults

            n_pts = ref.generateReferenceCurve()
            logger.info("Layer %d (z_mid=%.1f m): %d ref curve pts, τ_max=%.1f kPa",
                        i + 1, i * THICKNESS + THICKNESS / 2, n_pts, tau_max)

            # 6. MRDF curve fit
            fitted = layer.Curve.runCurveFit(FittingProcedureModel.MRDF_UIUC)
            logger.info("Layer %d: MRDF fit → %d points.", i + 1, fitted)

        # 7. Add ChiChi motion directory and select it
        model.Motions.addMotionDirectory(CHICHI_MOTION_DIR)
        model.Motions.refreshMotionsList()
        available = [m.name for m in model.Motions.listMotions()]
        logger.info("Available motions: %s", available)
        model.Motions.setMotionSelection([CHICHI_MOTION_NAME], selectOnlyListed=True)

        # 8. Save and compute
        model.saveAs(OUTPUT_PROJECT)
        compute_result = model.runCompute(timeout=3600)
        if not compute_result.success:
            raise RuntimeError(f"RunCompute failed: {compute_result.errorMessage}")
        if compute_result.partialSuccess:
            logger.warning("Partial success: %s", compute_result.errorMessage)

        # 9. Result path
        entry = model.Results.getResultDatabasePath(PROFILE_NAME, CHICHI_MOTION_NAME)
        print(f"\nResult database: {entry.resultDatabasePath}")
        print(f"Exists on disk:  {entry.resultDatabaseExists}")

    finally:
        model.close(saveProject=False)
        app.close()

if __name__ == "__main__":
    main()