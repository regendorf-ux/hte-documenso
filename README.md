# HTE Document Signing (HTE, Inc.'s copy of Documenso)

This is the source of the document-signing site that HTE, Inc. runs at **sign.htepr.com**. It is
[Documenso](https://github.com/documenso/documenso), the open-source document-signing platform, with HTE's
look on top:

- buttons and accents in the blue of HTE's logo, a navy top bar and HTE's logo;
- HTE's sign-in card ("Sign in with Microsoft" for HTE staff);
- a light / dark switch (it starts from the device's own setting);
- htepr.com's fonts (Archivo and Source Sans 3, both under the SIL Open Font License);
- a "Powered by Documenso · source" line on every page, linking here.

Nothing about how documents are signed, sealed or stored is changed.

## What is here

| | |
|---|---|
| `UPSTREAM` | the Documenso release this copy is built on |
| `patches/` | HTE's changes to Documenso's code (a plain `git diff`) |
| `overlay/` | files HTE adds or replaces: its logo, photo, fonts and tab icons |
| `tools/apply.sh` | puts `patches/` and `overlay/` on a checkout of Documenso |
| `test/` | the signing test: a sample service report signed by a technician, then a customer, through the same client HTE's service-report app uses |
| `.github/workflows/build.yml` | the weekly build: Documenso's latest release + HTE's changes, built, tested, published |

Each [release](../../releases) holds the image's digest, the test's results and pictures, and the complete
source that release was built from (`hte-documenso-<version>-source.tar.gz`).

## Building it yourself

```bash
git clone --depth 1 --branch "$(cat UPSTREAM)" https://github.com/documenso/documenso.git src
tools/apply.sh src
docker build -f src/docker/Dockerfile -t hte-documenso src
```

## Licence

Documenso is © Documenso, Inc. and contributors, under the GNU Affero General Public License v3
(`LICENSE`). HTE's changes are under the same licence. HTE's name and logo are HTE, Inc.'s and are not
part of that licence.
