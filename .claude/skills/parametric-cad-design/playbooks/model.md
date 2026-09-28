## Model

**form-fillets-shell-then-detail** - Consider shaping and filleting the outer envelope before shelling, then adding interfaces; choose the order for the wall and edits you need when a moulded or cast part is built; not for geometry or dependencies better served by another order. Prove: `model_measure_between`: the wall and interface dimensions after creation and a relevant size change.

**carve-do-not-accrete** - Extrude the block, loft or extrude the cutting form, split the block by it and remove the waste - the kept piece carries clean faces when the form is a block with a curved face or a tapered body; not for a form that is itself one extrude or revolve. Prove: `model_inspect`: one body left with the volume you expect after the split.

**one-half-mirror-combine** - Use a mirrored half when both sides must track, combining only a single physical part; otherwise express symmetry through suitable sketch or feature relationships when the part is symmetric; not for features whose independent requirements merely produce a symmetric shape today. Prove: `model_measure_between`: corresponding dimensions and positions remain symmetric after an intended change.

**pattern-only-identical-intent** - Build one and pattern it; copies answering different requirements are modelled apart when the same feature repeats; not for copies that merely share a shape. Prove: `design_get`: the repeated feature's definition; `model_measure_between`: member dimensions and spacing after a relevant count or size change.

**let-the-process-shape-the-part** - Choose draft, walls, radii, holes and fit clearance from the intended process and interfaces; identify provisional values rather than borrowing sample dimensions when the part will be manufactured; not for an unsettled process, which is stated rather than assumed. Prove: `find_geometry`: the relevant face normals, radii and interfaces against the stated process requirements.

**threads-by-intent** - Use model_thread for a standard call-out, with modeled=true when geometry is required; reserve custom helical construction for a nonstandard form or a demonstrated capability gap when a thread is needed; not for a thread represented only as an explicitly labelled envelope. Prove: `design_get`: the Thread feature and readable parameters; `model_measure_between`: mating dimensions of the claimed thread geometry.

**components-when-the-count-is-known** - Stay in bodies until the part count settles, then promote each body to a named component before any joint when bodies are still being carved out of one another; not for a part known from the brief, which starts as its own component. Prove: `assembly_get`: named parts, their ownership and the intended joint relationships; `model_measure_between`: the intended interface positions after a relevant edit.

### Recipes

#### One moulded shell construction

Use when a shell whose outer envelope is conveniently built before its wall; prepare the dimensioned sketches and choose a pull direction.

1. `model_extrude` - build the initial envelope from the prepared profile. Read back: its dimensions and intended body.
2. `model_fillet` - apply envelope radii that should precede the wall. Read back: the radii and resulting shape.
3. `model_shell` - open the required face and form the wall. Read back: the intended opening and remaining body.
4. `model_measure_between` - measure representative wall locations. Read back: thickness matches the requirement.
5. `model_extrude` - add required bosses or ribs from prepared sketches. Read back: the intended connections and affected bodies.
6. `model_draft` - apply required draft with the chosen pull direction. Read back: the resulting face directions.
7. `model_hole` - create the required interface holes. Read back: their size, position and depth.
8. `view_section` - section a wall and boss. Read back: view_screenshot shows the material connections; dimensions come from the measurements.

Bar - measure: measured walls and interfaces meet the requirements; added bosses and ribs are accounted for. Eyes: the outside and section show the intended shell and connected details.
Exemplar: Basket - Part (urn:adsk.wipprod:dm.lineage:ph2BLdbPShaZLqEV3FMLRg) - rows 0-19: Extrude, Loft, Split, RemoveBody, Draft, Fillet x4, then Shell1; bosses, drafts and a second shell follow. Access: Autodesk Design Samples; needs hub access, read only

#### One imported body with added interfaces

Use when an imported part whose supplied form should remain a reference; choose its component, placement and permitted interface changes first.

1. `model_create_component` - create the receiving component. Read back: its identity and ownership.
2. `model_base_feature` - open a base feature for the import. Read back: the active scope.
3. `doc_insert_import` - import into that scope. Read back: the actual imported bodies.
4. `model_base_feature` - close the base feature. Read back: the feature state.
5. `model_move` - apply the chosen placement if needed. Read back: model_inspect shows the intended position and bounds.
6. `sketch_create` - create a sketch on the intended interface support. Read back: its identity and frame.
7. `sketch_add_geometry` - draw the required interface layout. Read back: the curve identities.
8. `sketch_dimension` - dimension the required spacing and sizes. Read back: the evaluated dimensions.
9. `model_hole` - create the specified holes. Read back: their actual placement, size and depth.
10. `model_chamfer` - apply specified interface chamfers. Read back: the affected edges and resulting dimensions.
11. `model_measure_between` - check the interfaces. Read back: the required spacing and seating relationships.

Bar - measure: the permitted changes meet the interface dimensions and unrelated supplied geometry is preserved. Eyes: the placed part retains its reference shape outside the intended edits.
Exemplar: Main Support Skeleton (urn:adsk.wipprod:dm.lineage:3QrFqp9VRYepLTttp3M1yg) - seven rows: BaseFeature1, Align1, DeleteFace2, Sketch1, Hole1, Sketch2, Hole2 on a generative outcome. Access: Autodesk Design Samples; needs hub access, read only

#### One family using configurations

Use when variants share a useful parametric definition and configurations are available; prepare the component and profile sketch first.

1. `param_add` - create independent drivers and derived relationships. Read back: the expressions evaluate.
2. `sketch_dimension` - bind the intended profile dimensions to those drivers. Read back: the evaluated dimensions.
3. `model_revolve` - create the revolved form from the prepared profile. Read back: the intended solid and dimensions.
4. `doc_save_as` - save into the agreed destination before configuring. Read back: the saved document identity.
5. `design_configure` - create the required table, columns and variant rows. Read back: the declared rows and their values.
6. `design_configure` - activate another variant. Read back: the active row.
7. `model_inspect` - inspect the active variant. Read back: body bounds; design_get with tree_bodies=true confirms solid state, and model_measure_between checks other dimensions.
8. `design_get` - inspect dependent feature health. Read back: the intended features remain healthy.
9. `design_configure` - restore the required handoff variant. Read back: the active row and independently checked dimensions.

Bar - measure: the selected variants meet their dimensions and shared interfaces; health alone is not dimensional proof. Eyes: the variants visibly express the intended differences; labels are included only if required.
Exemplar: Configured Dumbbell (urn:adsk.wipprod:dm.lineage:0Unl7fg2Q2upJxRN-cdSfQ) - 12 parameters, urethane_coating = weight_width / 10, weight_text driving the emboss, 14 configuration rows. Access: Autodesk Design Samples, read only
