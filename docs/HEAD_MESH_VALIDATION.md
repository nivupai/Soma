# Synthetic head mesh validation — Milestone 27

Six independently seeded generated heads comprise two prolate, two oblate and two
smooth asymmetric examples. They are parameter draws within three fixed families,
not participant anatomies. Four interfaces represent brain/CSF/skull/scalp in MRI
RAS metres, with piecewise isotropic conductivities in S/m. See the frozen protocol
and its explicitly retained revision 2 for equations and seed schedules.

Each interface has 12/42/162/642 vertices and 20/80/320/1280 triangles at levels
0/1/2/3. Stored faces point outward; only the explicit OpenMEEG convention adapter
reverses their winding. Checks reject open, nonmanifold, degenerate, inconsistent,
inverted and self-intersecting boundaries, inter-interface intersections and
insufficient thickness. Existing Soma conservative broad-phase/exact triangle
feature-distance checks use 1e-8 m tolerance. These bounded checks are not a general
solid or human anatomical certification. No mesh is silently repaired.

Across every executed four-interface configuration, minimum separation was
1.110748 mm (frozen minimum 0.4 mm); minimum triangle quality was 0.953540
(minimum 0.2); maximum aspect ratio was 1.364665 (maximum 3.5). Interfaces were
single connected components with Euler characteristic 2, zero boundary and
nonmanifold edges, zero detected nonadjacent intersections and positive winding.
The public `models.json` retains every mesh fingerprint and detailed diagnostics.

The 48 inverse candidates use common 35/55 mm shells. All candidates satisfy the
2 mm margin in each estimated brain. Truth sources need satisfy the finest true
brain, not the different coarse estimated boundary. A geometric audit rejected
the original 60 mm candidate design before outcomes (one 1.63 mm margin); both
seals and amendment commits are retained. No head was removed.

Sensors are analytically targeted on the scalp and explicitly projected radially
to each triangulated scalp. Maximum projection was 19.493 mm at the very coarse
level, versus 0.414 mm on finest truth. This large coarse discretization is part
of the experiment, never an unnoticed sensor repair. Pose perturbations retain
their explicit HEAD→MRI transform and extra projection diagnostic. Explorer
meshes are separately labeled display examples; quantitative solves use their
recorded analysis level. There is no MRI segmentation, real skull thickness or
human sensor coregistration validation here.
