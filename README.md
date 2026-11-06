## Introduction

This project is a library that can be used to interact with RSSeismic through python.

| Resource | Link |
|----------|------|
| **Reference manual** | https://rocscience.github.io/rsseismic-scripting/ |
| **PyPI package** | https://pypi.org/project/RSSeismicScripting/ |
| **RSSeismic release notes** | https://www.rocscience.com/support/rsseismic/release-notes |
| **Program downloads** | https://www.rocscience.com/support/program-downloads |

### Goal

Each function exposed corresponds to an equivalent operation you could have done through the UI.
Using this idea, the user should be able to edit models and get results without having to go through the UI at all.
Although only a limited set of functionality is exposed for now, the library covers the main scripting workflows. For a list of what is exposed in the current library, see [Exposed Functionality](#exposed-functionality).

### Python UI equivalents

Events and workflows done in the UI will have equivalents in the Python library.
Wherever a dialog is shown in the UI, there will be an equivalent class with methods that mimic the dialog's behavior.
Wherever a warning or error dialog is displayed, an exception will be thrown, or a warning will be displayed in Python instead.
Wherever you can select and manipulate an entity, identifiers can be used in the library to get references to those entities in Python and objects will be constructed to help you interface with them.

### How it works

Each function in the library is a wrapper to make an API call to the application.
Objects retrieved through function calls will often not contain any data themselves, but will instead be proxies, allowing you to get information from the objects in the application.
For this reason, debugging will sometimes be tricky, as not all data will always be available for you to inspect unless you get it and assign it to a variable yourself.

### Warnings

References can be *invalidated* whenever the corresponding object in the application is destroyed or reloaded. You will need to watch out for expired references and renew them when needed as it can cause crashes or incorrect results if not managed properly.

## Exposed Functionality

The library exposes a focused set of RSSeismic workflows through Python. In this version you can:

- **Application connection**: Launch RSSeismic with the scripting server (`startApplication`), connect on a port, `ping`, open `.rsseismicfile` projects, create blank projects, adjust `maxConcurrentAnalyses`, run **batch compute** across many project files, and close the client connection.

- **Application preferences (`app.preferences`)**: Default unit system for new projects, maximum concurrent analyses during compute, and results working directory.

- **Motion library (`app.MotionLibrary`)**: Without an open project—convert plain-text or PEER AT2 files into Motion Manager folders, delete library motions, change Motion Manager display units, and open individual motions or horizontal pairs for analysis.

- **Ground-motion databases**: Sign in to GMDB, CESMD, or ESM, search with filters, and import records into a Motion Manager preference folder.

- **Target spectra and matching**: Build target spectra (user-defined, REXEL, or NSHMP), match horizontal motion pairs to targets manually or with automatic record selection, and read scale factors from the match results.

- **Motion and pair analysis**: Motion properties; time histories and response spectra as **pandas DataFrames**; amplitude scaling; baseline correction and timestep reduction; kappa estimation; pair geometric-mean spectra and effective amplitude spectra; discover H1/H2 pairs in a folder by shared file prefix.

- **RSLog (`RSLog`)**: Authenticate (including two-factor), list RSLog projects and boreholes, and import boreholes into the open project from RSLog or a JSON export.

- **Project lifecycle (`Model`)**: Save, save as, close, **run compute** (with optional timeout and partial-success handling), clear results, and automatic profile **generate** / **reset** when that feature is enabled on the project.

- **Profiles (`model.Profiles`)**: List, create, copy, delete, and rename profiles; active profile; list soil layers and bedrock; output depths; get **SoilLayer** / **BedrockLayer** property proxies.

- **Profile layer CRUD (`model.SoilLayers`)**: Insert, append, delete, duplicate, and move soil layers on the active profile.

- **Mean profile (`model.MeanProfile`)**: Structure CRUD on the automatic-generation template; **MeanProfileSoilLayer** properties including vary-with-depth shear wave / shear strength tables and **ReferenceCurve** (without auto-generate on template layers).

- **Profile generation settings (`model.ProfileGenerationSettings`)**: Typed getters/setters for randomization, profile count, and related generation parameters.

- **Project settings (`model.ProjectSettings`)**: Typed project properties (analysis mode, solver, motions configuration, automatic profile generation, etc.), plus **unit system** get/change.

- **Ground motions (`model.Motions`)**: Motion directory preferences (add/remove/list), refresh project motion list, **uni-directional** motion list/selection or **bi-directional** pair list/selection, select-all and per-directory select/deselect.

- **Damping formulation (`model.DampingFormulation`)**: Read and set project damping (frequency-independent or Rayleigh), apply recommended modal frequencies, and export damping-curve and frequency/time-domain solution tables as **pandas DataFrames**.

- **Layer properties**: **SoilLayer** (thickness, soil model, unit weight, …), **ReferenceCurve** (curve model, points, generate reference curve on profile layers), **SoilLayerCurve** (dynamics, discrete points, **curve fit** via `FittingProcedureModel`, including Rollins (2020) and Alemu (2025)), **BedrockLayer** on realized profiles.

- **Single-element test (`ElementTestLayer`)**: Create a single-element layer on the active profile, set layer properties, run the element test, and read strain-path results.

- **Results (`model.Results`)**: Result paths and database metadata; compute-aligned motion/layer discovery; **pandas DataFrames** for profile/layer time histories, profile summaries, result series (`ResultSeriesKind`), strain convergence, and real-time displacement; bulk fetch helpers for many motions/layers.

- **Public types and enums**: Summary dataclasses (`ProfileSummary`, `MotionInfo`, `ResultDatabaseInfo`, …), `ResultSeriesKind`, `ResultMotionType`, `UnitSystem`, and property enums under `rsseismic.enums` (for example `SoilModel`, `AnalysisMode`, `InputMotionConfiguration`, `FittingProcedureModel`).

For method-level detail, use the [Scripting reference manual](https://rocscience.github.io/rsseismic-scripting/) (API reference and example scripts).

## Getting Started

- **Getting started guide** 
https://www.rocscience.com/help/rsseismic/tutorials/scripting/getting-started-with-rsseismic-python-scripting
- **Tutorials** 
https://www.rocscience.com/help/rsseismic/tutorials/scripting/building-a-single-profile-and-running-an-analysis
https://www.rocscience.com/help/rsseismic/tutorials/scripting/building-multiple-projects-and-running-batch-processing
