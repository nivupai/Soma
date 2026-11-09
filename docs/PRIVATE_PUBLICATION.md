# Private publication and active checkout

This publication preserves all scientific commits and numerical results. A
separate, object-independent checkout was used to replace a private home-directory
prefix in four historical verification records with `<LOCAL_HOME>/`. Relative
scientific suffixes, dataset identifiers, source code, dependencies, numerical
values, author/committer attribution and commit order were preserved.

These placeholder paths describe the original execution environment; they are
historical provenance, not executable local paths. Content digests and original
execution commit IDs in scientific records were not retroactively regenerated.
History rewriting changes Git IDs. The confidential original-to-rewritten map
and original history backup are retained outside this published repository.
Legacy audit scripts that explicitly reference original Git IDs or private report
ledgers need that retained original context; the public checkout does not pretend
to have executed the historical studies under its rewritten commit IDs.

The publishing-safety commit adds ignore rules and this note. It does not change
a scientific method, test, dependency or clinical/inferential claim. The repository
must remain private; medical datasets, individual derivatives, local configuration,
credentials and confidential audit reports are not publication artifacts.

## Active working checkout

After the verified first publication, use the sanitized checkout for future work:

```sh
cd "$HOME/Documents/Soma-publish-clean"
git status
git remote -v
git branch --show-current
```

Its publication remote is named `github` and points to the private `nivupai/Soma`
repository. Review and commit normally, then use `git push github main` when
publication is explicitly authorized. Do not push, merge or import unsanitized
history from the original checkout into this branch.

The original checkout and the confidential backup remain intact. The backup at
`$HOME/Documents/Soma-publish-backup` intentionally contains unsanitized history.
Never commit or upload it. Private audit receipts, scanner reports, transformation
rules and commit mapping are kept there, outside the published tree.

Local scientific assets used for verification live only in ignored directories.
Configure their permitted roots explicitly when setting up Explorer; see
`EXPLORER_USER_GUIDE.md`. No medical data should be staged as a test workaround.

## Restoring the old pathname later

That is a separate migration requiring approval: stop the relevant local services,
verify both backups and the published head, retain the original directory under a
confidential archival name, then put a sanitized clone at the desired pathname.
Recreate local environments and ignored data-root configuration and rerun checks.
Do not delete, reset or silently replace the original repository as part of this
publication operation. No force push is required or authorized.
