## Manufacture

**rig-is-part-of-the-job** - Hold the fixture as its own components beside the part, select only the part body as the model, and take the work coordinate system from the stock; the fixture is geometry the toolpaths must avoid, not decoration when a setup is created; not for a setup sheet exercise with no fixture. Prove: `cam_get`: selected_models names the part only and the wcs origin_mode is stated.

**steep-and-shallow-are-two-strategies** - Parallel skips steep areas by default and 3D contour skips shallow ones; machineSteepAreas and machineShallowAreas extend their coverage; consider scallop for both, choosing its stepover for the tool and required finish when finishing a 3D form; not for a flat part, where face and 2D contour suffice. Prove: `cam_compare_operations`: the machineSteepAreas or machineShallowAreas difference in the pair; `cam_get`: the coverage controls and tool carried by each operation; `cam_show_toolpath`: the intended operation is shown in isolation; `view_screenshot`: visible passes on the intended regions.
Example: a stepover of a tenth of the tool is a sample setting, not a universal finish requirement.

**pocket-or-adaptive** - Adaptive takes deep stepdowns at a light radial load and needs no leads or compensation; 2D pocket takes shallow stepdowns with a finishing pass and cutter compensation - pick adaptive for bulk removal, pocket when the wall finish comes from the same operation when roughing a pocket; not for a slot, which wants the slot strategy on a closed slot contour. Prove: `cam_compare_operations`: optimalLoad and maximumStepdown on adaptive; finishing passes and compensation on pocket; `cam_get`: the geometry selections carried by each operation.

**geometry-selection-is-half-the-operation** - Compare their geometry selections - chains, extension modes, stock contours, boundaries - because a parameter diff cannot see them when two operations read as identical; not for operations that differ in parameters already. Prove: `cam_get`: each operation's references: the chains and faces it was given.

**turning-lead-out-gouges-the-remaining-stock** - Inspect the exit move and the stock the cycle leaves; turn the lead-out off, or leave allowance where a later pass removes it; regenerate and assess the result when a turning profile finishing cycle reports 'Lead-Out has been modified due to a gouge with the remaining stock'; not for a cycle whose exit move has to clear a face, where the lead-out is the point. Prove: `cam_get_status`: the warning after the change and whether the result is empty; `cam_show_toolpath`: the intended operation is shown in isolation; `view_screenshot`: the exit path against the part and displayed stock.
Example: measured on a turned flange: doLeadOut false, or useStockToLeave true with xStockToLeave and zStockToLeave at 0.5 mm, each cleared this warning.

**rest-stock-is-what-the-setup-before-left** - MEASURED on a turned flange, one whole-model adaptive with its parameters untouched: it generated EMPTY on that setup under previous_setup stock in both the 'rest' and 'setupStockSilhouette' modes, and the same operation cut 347 s the moment the setup alone was switched to a relative box. These stock extents keep the relative-box numbers and describe nothing this setup cuts, so size a clearing strategy from the preceding setup's own operations, not from these extents. An operation's OWN rest is a separate knob: defineStockBy 'rest' reads restMaterialSource 'previousOperations' - the operations before it in THIS setup, not the setup's stock mode - and with every sibling valid it computes, no 'Failed to generate rest material.' among the warnings when a milling setup takes stock_mode 'previous_setup' after a turning setup; not for the first setup of a job, whose stock is the billet. Prove: `cam_get`: the setup row reads stock_mode 'previous_setup' and stock_extents_describe says the box is not the stock; `cam_get_status`: whether the clearing operation is named in empty_toolpaths - the list reports membership, never why.

### Recipes

#### Choosing a strategy for a feature

Use when a prepared setup and tool library need a cutting operation for a known feature; choose from available strategies.

1. `cam_get` - read available strategies and setup context. Read back: the allowed candidates, model, stock and frame.
2. `find_geometry` - inspect the intended feature and access. Read back: its dimensions, geometry and directions.
3. `cam_create_operation` - create a candidate with a suitable tool. Read back: the operation and tool it carries.
4. `cam_select_geometry` - select the intended feature and boundary. Read back: the resolved selection.
5. `cam_generate` - generate the candidate. Read back: the handle; poll cam_get_status to completion and inspect errors.
6. `cam_inspect_toolpaths` - inspect validity and emptiness. Read back: the observed state; an empty result does not diagnose its cause.
7. `cam_get` - read warnings, heights and the time slice. Read back: the height settings and motion estimates.
8. `cam_show_toolpath` - show the candidate in isolation. Read back: view_screenshot supports coverage of the intended feature.
9. `cam_compare_operations` - compare a separately prepared alternative when the trade-off remains unclear. Read back: setting differences, with selection and coverage checked separately.

Bar - measure: the operation computes and evidence supports intended coverage; unexplained emptiness or warnings remain findings. Eyes: passes reach the intended feature with the planned entry and clearance.
Exemplar: 2D - Overview of toolpaths (urn:adsk.wipprod:dm.lineage:VJJsAJVXQmiDOFFl6-xErw) - 22 operations named for their variant, '2D Contour2' beside its multiple-passes, Trimmed and Rest siblings. Access: Autodesk Design Samples; needs hub access, read only

#### Checking a generated cutting operation

Use when a cutting operation expected to remove stock needs review before a demonstration post; machine release requires its own process checks.

1. `cam_get` - read the operation, tool, selections, heights and stock source. Read back: the actual settings and any freshness limits.
2. `cam_inspect_toolpaths` - read state and emptiness. Read back: the operation's computed state and whether it has a path.
3. `cam_get` - read warnings and motion estimates. Read back: time and distances; nonzero time alone does not prove stock removal.
4. `cam_show_toolpath` - show the operation alone. Read back: the visibility selection.
5. `view_screenshot` - inspect it against the feature, stock and fixture. Read back: visible coverage and clearance; unseen collisions remain unverified.
6. `cam_post` - post to the agreed output destination with the selected post. Read back: the reported file path and size, or refusal.
7. `cam_get` - re-read operation and program state. Read back: the delivered scope and any outstanding warning or stale state.

Bar - measure: report computation, coverage evidence and output delivery separately; a nonempty file is not proof of controller suitability. Eyes: the isolated path agrees with measured feature positions and heights; disclose what the view cannot establish.

#### Choosing a cross-hole approach

Use when a known hole crosses a turned axis; decide through/blind intent, entry side, access and required depth before selecting a setup.

1. `find_geometry` - inspect the hole and available entry geometry. Read back: the axis, position and relevant dimensions.
2. `cam_get` - inspect the available setup frames. Read back: whether an existing frame supports the intended approach.
3. `cam_create_setup` - create a dedicated setup only if the required approach needs one. Read back: the intended model and setup identity.
4. `cam_edit_setup` - bind the selected setup's orientation for that approach. Read back: the bindings and available frame values.
5. `cam_create_operation` - create a drilling cycle with the appropriate tool. Read back: the operation and tool.
6. `cam_select_geometry` - select the intended hole faces. Read back: the resolved faces.
7. `cam_edit_operation` - set the required heights and drilling depth. Read back: the actual height and depth settings.
8. `cam_generate` - generate and poll cam_get_status. Read back: the actual completion state and warnings; change orientation only if the evidence requires it.
9. `cam_show_toolpath` - show the operation in isolation. Read back: view_screenshot shows entry and depth against the measured hole.

Bar - measure: the generated approach and depth agree with the intended hole; through and blind cases have different acceptance. Eyes: the drill enters from the chosen side and reaches the specified depth.
