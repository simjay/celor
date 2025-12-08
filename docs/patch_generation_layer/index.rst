Patch Generation Layer
======================

The **Patch Generation Layer** is responsible for generating PatchTemplates with holes. This layer identifies what operations are needed and where holes should be placed, without needing to determine exact values.

Overview
--------

The Patch Generation Layer creates partially specified patches (PatchTemplates) that contain:

- **Operations**: What PatchDSL operations to apply (EnsureLabel, EnsureReplicas, etc.)
- **Holes**: Where uncertain values should be placed (marked with HoleRef)
- **HoleSpace**: The domain of possible values for each hole

This layer can generate templates from three sources (Fix Bank, LLM, or Default). For details on how templates are generated, see :doc:`template_generation`.

Key Properties
--------------

* **Minimal Token Usage**: Typically 1 LLM call (or 0 if Fix Bank hits)
* **Structure Focus**: LLM doesn't need to guess exact values, just operations and holes
* **Reusability**: Fix Bank enables cross-run learning
* **Domain-Agnostic**: Works with any domain that implements PatchDSL

Components
----------

.. toctree::
   :maxdepth: 1

   patch_dsl
   template_generation

Next Steps
----------

* Learn about :doc:`patch_dsl` for the PatchDSL language
* Understand :doc:`template_generation` for how templates are generated
* Explore :doc:`../cegis_layer/index` to see how templates are used in the CEGIS Layer

