# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'CeLoR'
copyright = '2024, Jaehyun Sim'
author = 'Jaehyun Sim'
release = '1.0.0'
version = '1.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
]

# Add sphinx_autodoc_typehints if available (optional dependency)
try:
    import sphinx_autodoc_typehints
    extensions.append('sphinx_autodoc_typehints')
except ImportError:
    pass  # Extension not available, continue without it

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# -- Extension configuration -------------------------------------------------

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Autodoc settings
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': False,  # Don't document undocumented members
    'exclude-members': '__weakref__,__dataclass_fields__,__dataclass_params__,__dataclass_transform__,__match_args__,__post_init__'
}

# Skip documenting dataclass fields in module docstrings to avoid duplicate warnings
# (They're still documented in API reference pages)
def skip_dataclass_fields(app, what, name, obj, skip, options):
    """Skip dataclass fields to avoid duplicate documentation warnings."""
    # Skip dataclass fields when documenting modules (not classes)
    # This prevents duplicate warnings when the same fields are documented in API reference
    if what == "attribute":
        # Check if this is a dataclass field by looking for __dataclass_fields__
        if hasattr(obj, '__annotations__') or (hasattr(obj, '__class__') and hasattr(obj.__class__, '__dataclass_fields__')):
            # Only skip if we're in a module context (not class context)
            # This is a heuristic - if the object has a __module__ attribute pointing to our modules
            if hasattr(obj, '__module__') and 'celor.core' in str(getattr(obj, '__module__', '')):
                return True
    return skip

def setup(app):
    app.connect('autodoc-skip-member', skip_dataclass_fields)

# Autodoc type hints
autodoc_typehints = 'description'  # Put type hints in description, not signature
autodoc_typehints_description_target = 'documented'

# Suppress warnings
# Only suppress warnings that are expected and cannot be fixed
suppress_warnings = [
    'app.add_directive',  # Sphinx extension directive warnings (harmless)
]

# Suppress expected import failures when optional dependencies aren't installed
# This is expected in CI/CD environments where not all dependencies are available
import warnings
warnings.filterwarnings('ignore', message='.*failed to import.*')


# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

# Todo extension
todo_include_todos = True
