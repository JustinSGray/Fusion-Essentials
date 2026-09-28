## Surface

**skin-first-solid-later** - Consider surfaces when their sections and boundaries express the form well; stitch or thicken at boundaries that support the intended edits when the outer form is the product; not for a solid or Form representation that better serves the same requirements. Prove: `design_get`: with tree_bodies=true, the selected body is_solid after relevant edits; `model_inspect`: body bounds against the intended dimensions.

**extend-before-trim** - Provide enough intersection for the intended trim and possible edits; extend only when the existing cutter does not provide it when one surface will trim another; not for a cutter that already overhangs. Prove: `model_inspect`: the retained body's bounds against the intended extent; `find_geometry`: retained face and edge locations; preservation beyond these observations remains unverified; `view_screenshot`: the retained region against the intended boundary.

**blend-by-split-and-loft** - Consider split-and-loft or a radius-controlled fillet; choose the construction for the required continuity and shape controls when two skins must meet with a smooth transition; not for a transition with no smoothness requirement. Prove: `model_measure_continuity`: gap, normal angle and curvature jump sampled along the seam against the required continuity.

**master-skin-derived-into-parts** - Consider a shared master skin when several parts must follow the same form; choose same-document or derived ownership for the intended reuse and revision process when several parts share one outer form; not for independently designed forms that merely touch. Prove: `model_measure_between`: the mating surfaces still agree after a shared-form change and update.

**peel-a-solid-to-a-skin** - Delete the faces you do not want; the remaining skin is the surface to build on when the quickest form is a solid but only some faces are wanted; not for a solid you will keep whole. Prove: `design_get`: the tree's body row reads is_solid false after the delete.

### Recipes

#### One bottle skin assembled from surfaces

Use when a changing-section container; prepare compatible body/neck profiles, rails, a crown profile and any required closure surfaces.

1. `model_loft` - loft the body skin from the prepared sections and rails with as_surface=true. Read back: the surface body and its intended boundaries.
2. `surface_revolve` - form the crown from its prepared profile and axis. Read back: the crown surface.
3. `surface_extend` - extend the cutter only if the intended intersection needs it. Read back: the resulting reach.
4. `surface_trim` - trim to the intended meeting boundary. Read back: the retained regions.
5. `model_stitch` - stitch enclosing surfaces within the permitted joining error. Read back: whether it closed and the free edges left; resolve missing boundaries before shelling.
6. `model_measure_continuity` - measure any seam whose continuity is required. Read back: sampled gap, normal angle and curvature jump against that requirement.
7. `model_shell` - form the required wall and mouth opening. Read back: the resulting body and opening.
8. `model_measure_between` - check wall and mouth interfaces. Read back: the dimensions against the requirement.
9. `view_screenshot` - inspect the form. Read back: the intended silhouette and visible transitions.

Bar - measure: the enclosing body and wall meet the chosen dimensions; claim continuity only where model_measure_continuity has measured the seam. Eyes: the skin and crown meet without an unintended visible break.
Exemplar: Bottle (urn:adsk.wipprod:dm.lineage:NX9msEStSlaONb6W4KI4ZA) - Sweep1 with a rail, Top_Crown on projected edges, Extend 5 mm before Trim, Stitch 0.10 mm, chord fillets, OffsetFaces -0.05 mm. Access: Autodesk Design Samples, read only

#### One shared skin derived into parts

Use when separate part documents must follow one master skin; prepare the master's sections/rails and each part's closing boundaries.

1. `model_loft` - create the master skin from the prepared references with as_surface=true. Read back: the intended surface body.
2. `model_mirror` - mirror a half skin when this construction uses symmetry. Read back: the matching skin geometry.
3. `model_stitch` - join the required skin pieces. Read back: the intended body and open boundaries.
4. `doc_save_as` - save the master in the agreed destination. Read back: the source document identity.
5. `doc_insert_derive` - derive the skin into each prepared part document. Read back: the body and source identity.
6. `surface_extrude` - create a closing surface from the prepared boundary. Read back: the surface intersects the intended skin region.
7. `surface_fill` - keep the intended enclosed cell. Read back: the resulting solid.
8. `model_shell` - form the required wall. Read back: the wall and openings.
9. `model_measure_between` - measure mating interfaces. Read back: the intended fit; revise only where its specified clearance requires it.

Bar - measure: parts meet their wall and interface requirements; verify shared-form changes if that dependency is claimed. Eyes: the parts assemble into the intended form with the specified interface gaps.
Exemplar: Mouse ASM (urn:adsk.wipprod:dm.lineage:u9j3iHSpRTq4-_zqT1ukdw) - the Mouse master's five named profiles; Base, Middle and Top each open with Context1 (derive) and BoundaryFill1. Access: Autodesk Design Samples, read only
