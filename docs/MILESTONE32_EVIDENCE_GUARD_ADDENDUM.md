# M32 evidence-domain guard correction

Final review after the initial PR publication identified an invalid-input gap in the
new readiness classifier: it accepted Dice >1 and Boolean metric values, and treated
whitespace/nonstring provenance as evidence. This correction requires real finite
Dice in [.8,1], non-Boolean HD95 in [0,5] mm and nonblank string provenance. It strengthens
intrinsic metric-domain validation; the frozen .8/5 mm scoring targets are unchanged.
A regression exercises impossible and mistyped evidence against an otherwise valid
three-boundary reference receipt. Such cases must be NOT_READY, never VALIDATED.

The actual study has no independent conductor references and takes the QC-only branch.
No historical scientific result, frozen design, mesh input, numerical tolerance,
segmentation prediction or M33 uncertainty family changes. A new exact-code human
replay and complete software/package/CI verification bind the correction to the final
publication head; earlier run receipts remain local and the Git history remains intact.
