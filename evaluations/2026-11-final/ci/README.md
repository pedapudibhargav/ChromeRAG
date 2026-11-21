# One-off CI extraction runs

Two baselines need packages that are not installed in the local evaluation environment, so each was run
once on a clean GitHub-hosted Ubuntu runner. Each workflow installs one pinned package, clones the public
WCXB benchmark (CC-BY-4.0), extracts the 511 test pages and uploads the outputs as an artifact. The outputs
were then scored locally with the same scorer as every other tool (`poc/revision_rows.py`).

| Folder | Package | Run date | Result file |
|---|---|---|---|
| `boilerpy3/` | boilerpy3 1.0.7 (Default and Article extractors) | 2026-11-20 | `../results/revision_rows/p13_boilerpy3.json` |
| `rs-trafilatura/` | rs-trafilatura 0.1.1 | before the 0.1.5 freeze | `../results/wcxb_test/wcxb_test.json` |

These files are the record of what ran. They are not active workflows in this repository (they are not
under `.github/workflows/`). `boilerpy3/hash_split.py` prints a SHA-256 digest of the upstream test split;
on the BoilerPy3 run it matched the local copy (1,022 files,
`eea9c654ba6f722ab6edcbaa9067490e23cdc6430c5ce22f1bca2c15b828d91b`).
`boilerpy3/boilerpy3_meta.json` holds the package version and per-page extraction times.

The benchmark address in `rs-trafilatura/extract.yml` is the one recorded at the time. The benchmark is now
at `https://github.com/Murrough-Foley/web-content-extraction-benchmark`, as in `boilerpy3/extract.yml`.
