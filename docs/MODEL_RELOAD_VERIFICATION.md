# Independent model reload verification

Training-session prediction output is captured before the estimator object is
released. Each numeric capsule is independently read and its labels compared
exactly. Decision/probability comparisons use the prespecified rtol1e-9/atol1e-9;
exact agreement and maximum absolute errors are recorded separately. MDM has no
supported probability output. Input/probe hashes and protocol identity are checked.

The private probe contains physical epochs, previously computed log-power/covariance
features and the original predictions. It verifies fitted-state reproduction and
feature contract identity, rather than independently repeating EDF preprocessing.
Existing preprocessing/feature numerical tests remain authoritative for that stage.

A distinct process from a separate working directory loads a noneditable Soma wheel.
The verifier disables Pipeline, LR, LDA, CSP, covariance, MDM and tangent fit methods.
It imports no in-memory training estimator, cache object or training-session global.
A second process restart repeats the test and writes another immutable receipt.

A normally resolved fresh installation was correctly refused: nibabel resolved
5.5.0 instead of training5.4.2 and installation-record hashes differed. That
execution remains unsupported by the default policy. It is not silently accepted
because predictions might look similar.

For exact reproduction, an additional isolated virtual environment receives a
faithful byte-for-byte private snapshot of the training dependencies, followed by a
fresh noneditable Soma wheel installation. Soma/services source code, editable hooks,
PYTHONPATH additions and training objects are excluded from the dependency snapshot.
The actual model remains a separate bounded numeric artifact. This preserves the
existing environment guard; installation records are not normalized, forged or
replaced with invented identities. Dependency files and metadata are copied together.
The fresh-package checks with ordinarily resolved dependencies remain separate.

This verifies a specific preserved numerical environment. It does not establish
universal model portability, independent biology or permission to interchange
scientific caches. Four-platform CI independently fits/reloads fictional releases
on macOS arm64/Linux x86_64 Python3.11/3.12 and tests tampering/contract rejection.
It never receives human recordings or real-data weights.

Actual restart receipts, tolerances, environment/build identities and inspected
errors are summarized in the milestone results and retained privately. Failed
attempts are retained as limitations, not relabeled successful execution.
