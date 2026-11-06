# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from datetime import datetime

# Specify the directory path
directory_path = os.path.abspath(os.path.join('..', 'src'))

# Add the directory path to sys.path
sys.path.insert(0, directory_path)

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'RSSeismic Scripting Reference Manual'
copyright = f'{datetime.now().year}, Rocscience Inc.'
author = 'Rocscience Inc.'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc',
              'sphinx_copybutton',
              'sphinx.ext.napoleon',
              "myst_nb"]

autodoc_default_options = {
    'member-order': 'bysource',
}

# Explicitly state the format of documentation
napoleon_google_docstring = True
napoleon_use_param = True
napoleon_use_ivar = True

exclude_patterns = ['_build',
                    'generatedAPIDocFiles/modules.rst',
                    'example_code/example_tri_directional_fem_workflow.rst',
                    ]

# -- Options for LaTeX output -------------------------------------------------
latex_elements = {
    'papersize': 'letterpaper',
    'pointsize': '10pt',
    'preamble': '',
    'figure_align': 'htbp'
}

autodoc_mock_imports = [
    'grpc',
    'google',
    "google.protobuf",
    "rsseismic.generatedFiles",
    "pandas",
    "matplotlib",
]

html_logo = "_static/rocscience-logo-primary.png"

html_favicon = "_static/rocscience_favicon.png"

html_theme = "pydata_sphinx_theme"

nb_execution_mode = "off"  # notebooks are already run
