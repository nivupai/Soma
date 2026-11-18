# Independent FEM forward reference

The optional `fem` extra pins scikit-fem 12.0.2. Its numerical Python package is
BSD-3-Clause licensed; SciPy performs sparse pivoted LU. Soma adds the EEG-specific
full-subtraction load and restricted conforming radial mesher. This is independent
Galerkin volume assembly, not an OpenMEEG wrapper or an established EEG solver
certification. Native FEniCSx/GetDP were not required to establish the small validated
reference. No third-party implementation source is vendored.

The continuous problem is ∇·(σ∇φ)=∇·Jp with isotropic piecewise σ, continuity of
potential and normal current, and zero outer current. A continuous P1 H1 space
imposes potential continuity; the conductivity-weighted weak form imposes interface
flux continuity weakly. The natural outer boundary is insulating. A pinned correction
DOF fixes a gauge, not a grounded physical scalp boundary. Final sensor averaging
removes the gauge consistently with BEM.

For a dipole at x0 with moment p in A m and local conductivity σ0 in S/m,
u∞=p·(x−x0)/(4πσ0|x−x0|³). The infinite-medium singularity is treated analytically.
The correction equation is

A(uc,v)=−∫Ω(σ−σ0)∇u∞·∇v−∮∂Ωσ0(n·∇u∞)v.

The contrast volume integral is evaluated only outside the source's constant brain
compartment. Its singularity is not sampled, regularized into a nodal load or moved
to a nearby vertex. The total electrode field is u∞+uc in V/(A m), source-major XYZ.
Arbitrary signed dipoles are explicit linear combinations in the same MRI/RAS metre
frame. There is no finite source cloud or selected source-radius fitting parameter.
Quadrature, polyhedral geometry and P1 correction discretization remain errors.

The discrete compatibility defect |sum(b)|/||b|| is retained before subtracting
its algebraic mean. Defects above 1e-3 reject the solve. The full residual ||Au−b||/||b||
is reported after compatibility correction; it is not a spatial-error estimate.
The central and multiple off-center analytical sphere controls test the actual
boundary potential, not merely current balance or agreement with OpenMEEG.

A separate concentric harmonic transmission reference solves seven coefficients
per degree: a_l r^n+b_l r^(−n−1), fixed inner singular coefficient, six potential/current
transmission equations and zero outer flux. It uses no MNE sphere approximation or
OpenMEEG matrix. Equal conductivities recover the independently tested homogeneous
solid-harmonic derivative series. Terms 48 and 96 are compared for truncation.
The general nonspherical FEM remains approximate even when the concentric series
is converged. This reference does not establish human anatomical accuracy.

The mathematical source treatment follows the full-subtraction formulation of
[Wolters et al., SIAM J. Scientific Computing](https://doi.org/10.1137/060659053).
Implementation and license references: [scikit-fem documentation](https://scikit-fem.readthedocs.io/)
and [BSD-3-Clause license](https://github.com/kinnala/scikit-fem/blob/master/LICENSE).
