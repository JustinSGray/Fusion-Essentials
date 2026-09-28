## Assemble

**one-assembly-idiom** - Choose relations for its actual freedoms and reference path; avoid duplicate constraints, while allowing independently organized subassemblies to use different constructions when defining relationships within a mechanism; not for a placement study that makes no kinematic claim. Prove: `assembly_get`: the intended freedoms, health and component poses rather than a preferred joint count.

**connected-reference-path** - Establish one intentional reference path from the grounded part; do not ground parts to hide missing joints when an assembly has a fixed moving mechanism; not for floating or multiple independent mechanisms. Prove: `assembly_get`: one ground_to_parent root and every joint reachable from it.

**as-built-for-parts-modelled-in-place** - Consider as-built joints to retain a deliberate placement; choose geometric joint references where they better express how interfaces must follow edits when a part was modelled against its neighbours where it sits; not for a static placement with no required joint relationship. Prove: `assembly_get`: the intended relative pose and motion limits; `model_measure_between`: mating dimensions after relevant edits.

**align-knobs-not-spacers** - Use the joint's align angle and align offset; do not add spacer bodies to fix a pose when a joint needs a flip or an offset; not for a real spacer part in the bill of materials. Prove: `assembly_get`: the joint's frame sits where the offset put it, and the occurrence list holds no spacer that is not a real part.

**exercise-the-mechanism** - Drive it to home and a representative extreme; keep moving joints few, the rest rigid; link two joints with a motion link when one motion implies the other when the mechanism has a driven joint; not for a joint with no travel of interest. Prove: `joint_drive`: the value at each pose; `assembly_inspect_interference`: overlaps at each pose, intended fit or defect.
Example: a nut overlapping a plain shaft is a thread modelled as a cylinder.

**fasteners-mint-parameters** - Expect a set of adsk_ parameters per fastener and read only the authored set; name each fastener instance by its spec when library fasteners are inserted; not for a design with no library parts. Prove: `param_get`: the authored user parameters are what comes back and generated_skipped counts the adsk_ ones the fasteners minted; include_generated=true lists those.

### Recipes

#### One in-place part with an as-built joint

Use when a part is designed in its intended assembled pose; prepare its component/sketch and identify the actual members and required freedoms.

1. `sketch_project` - project the relevant interface geometry into the prepared sketch. Read back: the intended references and links.
2. `sketch_add_geometry` - draw the chosen profile around those interfaces. Read back: the intended regions.
3. `sketch_constrain` - apply the required interface and shape relations. Read back: the accepted relations.
4. `sketch_dimension` - dimension the independent sizes. Read back: the solved dimensions.
5. `model_extrude` - create the part at its intended thickness. Read back: the body and affected scope.
6. `joint_create_as_built` - join the actual member pair with the intended freedom, without redundant bearing joints. Read back: the joint type and retained pose.
7. `joint_edit` - set the required travel limits. Read back: the limits.
8. `joint_drive` - exercise a representative pose. Read back: assembly_get shows the intended component motion.
9. `assembly_inspect_interference` - inspect that pose. Read back: overlaps classified against intended fits.
10. `joint_drive` - restore the handoff pose. Read back: assembly_get shows the restored position.

Bar - measure: the member has its intended motion and interfaces at the tested poses; untested travel remains unverified. Eyes: the part engages its interfaces and moves as intended.
Exemplar: bike frame (urn:adsk.wipprod:dm.lineage:ghXi2gxeQWqAdfsv8o1MOA) - rows 111-124: ROCKER sketched between bearings, three as-built joints, extrude, fillet, mirror, holes, a fourth as-built joint. Access: Autodesk Design Samples; needs hub access, read only

#### Coupled rotation and travel on separate members

Use when distinct rotating and translating members need an ideal pitch relationship; this does not model one cap both turning and advancing.

1. `assembly_get` - identify the reference member, moving members and existing freedoms. Read back: distinct members with the intended placements.
2. `assembly_ground` - anchor the chosen reference if the mechanism requires it. Read back: isGroundToParent confirms the chosen reference is anchored to its parent.
3. `joint_create_as_built` - give the rotating member its required revolute relationship. Read back: the joint type and retained pose.
4. `joint_create_as_built` - give the translating member its required slider relationship. Read back: the joint type and retained pose.
5. `joint_motion_link` - couple the two using the intended pitch and the tool's stated ratio units. Read back: the actual link and ratio; assembly_get records both starting joint values and member poses.
6. `joint_drive` - change the rotating joint from its recorded starting angle within the intended travel. Read back: assembly_get reports both member poses and the travel change.
7. `joint_drive` - drive that same joint back to its starting angle. Read back: assembly_get confirms both members restored.

Bar - measure: measured rotation and translation match the declared pitch; the ideal motion link does not prove a physical drive train. Eyes: each actual member moves as specified without substituting one member for another.
