## Sketch

**construction-carries-symmetry-and-spacing** - Draw the construction line, then constrain: symmetry about it, midpoint on it, equal between the members; dimensions pin only what remains when a profile has symmetry, equal spacing or a family of equal features; not for a one-off reference sketch. Prove: `sketch_get`: the intended relations, evaluated dimensions and remaining freedom; test symmetry or spacing after a relevant edit.
Example: a knife layout: 43 constraints, 5 dimensions; a handle profile: ten symmetry constraints, six expressions.

**anchor-to-the-origin-by-relation** - Put the origin on a midpoint or at the crossing of two construction diagonals, never at a typed coordinate when a profile is placed; not for geometry projected from a body, which is already placed. Prove: `sketch_get`: a midpoint or coincident constraint naming the origin point.

**one-literal-per-wall** - Type it once and write the other dimensions as that dimension's name (d239) or a named parameter when the same size appears twice; not for two sizes that only happen to match today. Prove: `sketch_get`: dimension expressions referencing a name, not a repeated number.

**organic-outlines-are-control-point-splines** - Draw a control-point spline and make its ends smooth to construction lines whose angles and lengths are dimensioned; the control polygon, not the curve, carries the intent when an outline is a free curve; not for a one-off path nothing else references, where a fit-point spline is enough. Prove: `sketch_get`: a cv_spline with 'smooth' constraints to lines that carry angle dimensions.

**detail-on-projected-edges** - Project the wall's edges into the sketch and dimension the detail by offset from them; projected geometry has no freedom, so few constraints fully constrain the sketch when a clip, rib or pocket must follow an existing wall; not for detail on a plane no body touches. Prove: `sketch_get`: projected references, evaluated offset dimensions and remaining freedom; full constraint is a diagnostic; `model_measure_between`: the resulting detail offset from its supporting wall after a relevant edit.

**driven-dimensions-are-checks** - Add it as a driven dimension and read it back; a master sketch may stay not fully constrained only where its free entities are the splines when a derived length or angle matters to the brief; not for a sketch nobody will edit. Prove: `sketch_get`: dimensions with driving=false carrying the value the brief asked for.

### Recipes

#### One anchored, symmetric profile

Use when a planar profile whose halves must track; choose its component, sketch plane and intended symmetry first.

1. `sketch_create` - create the profile sketch on the chosen plane. Read back: the sketch identity and frame.
2. `sketch_add_geometry` - draw construction references and both outline halves with approximate placement. Read back: curve identities and closed regions where intended.
3. `sketch_constrain` - apply the required anchor, symmetry, tangency and equality relations. Read back: the accepted relations.
4. `sketch_dimension` - dimension independent sizes and reference shared values by expression. Read back: the dimension names and evaluated values.
5. `sketch_get` - inspect the solved profile. Read back: dimensions, expected profiles and any unexplained freedom.
6. `param_set` - change one driver within its intended range. Read back: sketch_get shows both halves following the intended relationship.
7. `param_set` - restore the driver. Read back: sketch_get confirms the baseline dimensions and healthy profile.

Bar - measure: the profile meets its dimensions and intended symmetry through the change and restore. Eyes: the profile has the intended silhouette and placement.
Exemplar: Configured Dumbbell (urn:adsk.wipprod:dm.lineage:0Unl7fg2Q2upJxRN-cdSfQ) - Handle/Sketch1 - 17 lines held by 10 symmetry constraints and 6 expressions such as length_handle / 2 + length_thread. Access: Autodesk Design Samples; needs hub access, read only

#### One tangent link profile

Use when a web joining bosses; first create a sketch with resolved pivot references and decide which dimensions must track.

1. `sketch_add_geometry` - draw bore and boss circles plus construction references. Read back: the curve identities.
2. `sketch_constrain` - anchor bore centers to the pivot references and make each boss concentric. Read back: the accepted relations.
3. `sketch_add_geometry` - draw web flanks and any closing arcs required by the chosen outline. Read back: the curve identities.
4. `sketch_constrain` - constrain intended tangencies and endpoint connections. Read back: the accepted relations.
5. `sketch_dimension` - dimension bores, bosses, spacing and required arc radii. Read back: the evaluated dimensions.
6. `sketch_get` - inspect the regions to be used by the feature. Read back: the intended closed regions, dimensions and remaining freedom.

Bar - measure: the selected regions form the intended web and bores at their required positions. Eyes: the outline connects the bosses without unintended gaps or material.
Exemplar: bike frame (urn:adsk.wipprod:dm.lineage:ghXi2gxeQWqAdfsv8o1MOA) - ROCKER/Sketch1 - three bores, eight tangent constraints, one R70 closing arc, four dimensions. Access: Autodesk Design Samples; needs hub access, read only

#### One controlled organic outline

Use when a free outline needing controlled end tangency; first create its sketch and decide which parts of the shape must be editable.

1. `sketch_add_geometry` - create a control-point spline with enough controls for the shape. Read back: the actual degree and control polygon identities.
2. `sketch_add_geometry` - create construction guides for the required end directions. Read back: the guide identities.
3. `sketch_constrain` - connect the guide endpoints to the curve and apply the supported smoothness relations. Read back: the accepted relations; investigate a refusal before dependent edits.
4. `sketch_dimension` - dimension the guides and independent control sizes. Read back: their evaluated values.
5. `sketch_dimension` - add a driven check where a derived dimension matters. Read back: the driven value.
6. `sketch_get` - inspect the outline and its constraints. Read back: the intended controls and any deliberate remaining freedom.

Bar - measure: dimensions and end directions meet the requirement; claim only the continuity actually measured. Eyes: the curve has the intended silhouette and no unintended kink.
Exemplar: Mouse ASM (urn:adsk.wipprod:dm.lineage:u9j3iHSpRTq4-_zqT1ukdw) - Mouse/Side Profile - a degree-5 spline G2-smooth to guides at 35, 40, 30 and 50 deg; Top Profile the same at degree 7. Access: Autodesk Design Samples; needs hub access, read only
