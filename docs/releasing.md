# Releasing

Releases follow [Semantic Versioning](https://semver.org/). The version lives in one place,
`pylogkit/_version.py`, and the build reads it from there.

## Cutting a release

1. Move the entries under `## Unreleased` in `CHANGELOG.md` into a new `## X.Y.Z - YYYY-MM-DD`
   heading, and leave an empty `## Unreleased` section above it.
1. Set `__version__` in `pylogkit/_version.py` to `X.Y.Z`.
1. Open a pull request with those two changes and merge it once CI is green.
1. Tag the merge commit and push the tag:

    ```bash
    git tag -a vX.Y.Z -m "Release X.Y.Z"
    git push origin vX.Y.Z
    ```

Pushing a `v*` tag runs `.github/workflows/release.yml`. It checks that the tag matches
`__version__`, builds the sdist and wheel, runs `twine check`, and attaches both to a GitHub release
whose notes are generated from the merged pull requests.

## Publishing to PyPI

The workflow does not publish to PyPI yet. The name `pylogkit` is already used there by an
unrelated project (see issue #44), so a distribution name has to be chosen first. Once it is,
add a publish job that uses
[trusted publishing](https://docs.pypi.org/trusted-publishers/) with the `id-token: write`
permission, so that no API token is stored in the repository.
