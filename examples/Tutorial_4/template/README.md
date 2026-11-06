# Tutorial 4 auto-profile template

Tutorial 4 can build a FEM project with **automatic profile generation** when you pass
`--randomize` (or enable the randomization path in the script). That flow needs a saved
RSSeismic project with automatic profile generation already configured.

## Options

1. Copy `Test_Auto_Profile.rsseismicfile` from your local `tests/resources/` folder
   (see `tests/resources/README.md`) to this directory as
   `tutorial_4_auto_profile.rsseismicfile`.

2. Set the environment variable `RSSEISMIC_AUTO_PROFILE_TEMPLATE` to the full path of
   any suitable template project.

3. Pass `--template path\to\project.rsseismicfile` on the command line.

Without a template, run Tutorial 4 **without** `--randomize` to use the single-profile
CSV path documented in the script.
