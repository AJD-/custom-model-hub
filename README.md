# Custom Model Hub

Reviewed model packs for the [Custom NPC Models](https://github.com/AJD-/CustomNPCModels) RuneLite
plugin. Switch on `Enable Custom Model Hub` in the plugin's settings, and its side panel lists every
pack here, to install, update or remove.

Each pack lives on its own branch, `pack-<id>`. The `manifest` branch holds `manifest.json`, which
the plugin reads, and which a workflow rebuilds from the pack branches.

## What a pack branch holds

The files sit at the branch root. Outside `source/` and `notes/`, **Check pack** refuses any file
not listed here.

### Required

| File | |
|---|---|
| `pack.json` | Written by `generateAssets -PpackOut`, never by hand. It needs an `id`, `name`, `author`, `version` and `license`, and a `models` list that isn't empty, each model with a `key`, `name` and `npcIds`. `description` is optional, and `tags`, when given, is a list of strings. |
| `bundle.dat` | Built with `generateAssets -PpackOut`. A gzipped bundle, 1 byte to 16 MiB. |
| `ABOUT.md` | What the pack changes, and what it was made from. |
| `LICENSE` | The license the pack is published under. |
| `source/models.json` | The manifest the pack is built from. Its `pack` block's `id` must be `pack.json`'s. |
| `source/*.glb` | Every model `source/models.json` names, so the pack can be reviewed and rebuilt. |

### Optional

| File | |
|---|---|
| `icon.png` | A real PNG, ideally 128 × 128. At most 512 pixels a side and 256 KiB, or it isn't shown. |
| `source/<name>.retarget.json` | Run through `retargetGltf` first, from `source/<name>.glb` beside it into `source/<name>-retargeted.glb`. A committed `source/<name>-retargeted.glb` must be exactly what that makes. |
| `notes/` | Anything that explains the pack, such as renders or the scripts behind its choices. It isn't built. |
| `.gitattributes` and `.github/` | As `pack-empty` has them. Leave them be. |

The pack `id` is 1 to 64 lowercase letters, digits and hyphens, and its branch is `pack-<id>`. It may
not start with `dl-` or be a name Windows reserves.

`pack.json` is built from the `pack` block of `source/models.json`, so that is where its fields go.
`generateAssets` needs only an `id` and `name` there, but Check pack also wants an `author`, `version`
and `license`:

```json
{
  "pack": {
    "id": "my-mole",
    "name": "My mole",
    "author": "You",
    "version": "1.0",
    "description": "A Giant Mole in a party hat.",
    "license": "CC-BY-4.0",
    "tags": ["moles"]
  },
  "models": [ ... ]
}
```

The plugin only downloads `bundle.dat` and `icon.png`. What its panel shows about a pack comes from
the manifest, which is built from `pack.json`.

A pack can also be loaded without the hub, from a folder in the plugin's local packs folder. There
only `bundle.dat` is needed, and `pack.json` is optional.

## How to submit

1. Fork this repository with all branches, and check out `pack-empty`.
2. Create a branch `pack-<your id>`, add the files above, and push it. Don't change `.github/`.
3. Open a pull request against `pack-empty`.

The **Check pack** workflow runs on the pull request, and a maintainer reviews it. Once accepted, the
pack gets its own `pack-<id>` branch here and appears in the manifest.

To update a pack, open a pull request against its `pack-<id>` branch with the rebuilt files and a
new `version`.

## Review rules

- **Your own work, or the game's own.** Packs made from the plugin's `exportGltf` output (recolored,
  edited or retargeted) are accepted, and their ABOUT.md must say what they were made from. Nothing
  from another game, and nothing of someone else's without their permission.
- **Jagex assets stay Jagex's.** A pack's license may cover only its own work. Packs that use game
  assets carry this notice in their ABOUT.md and LICENSE:
  > This is not affiliated with, authorized, maintained, or endorsed by Jagex. Old School RuneScape
  > and all associated visual assets, trademarks, and copyrights are the sole property of Jagex.
- **No adult content.**
- **No NPCs the plugin never swaps**: the Inferno, the Fight Caves, the TzHaar fight pits,
  TzHaar-Ket-Rak's challenges, the Fortis Colosseum, and their Deadman copies. `generateAssets`
  refuses to build a pack that names them.

## What CI checks

**Check pack** runs on pull requests against `pack-empty`, and on pushes to `pack-*` branches:

- The layout: only the files above, `pack.json` complete, the branch named after the id, and
  `bundle.dat` and `icon.png` within the plugin's limits. Sources that look like exports from the game
  cache are noted in the run summary, so the reviewer can check that ABOUT.md says so. They aren't
  refused.
- That the pull request leaves `.github/` as `pack-empty` has it.
- The rebuild. The Custom NPC Models tools, at the commit pinned in the workflow, rebuild the pack
  from `source/` against the newest Old School live cache in the [OpenRS2 archive](https://archive.openrs2.org/).
  `bundle.dat` must match once decompressed, and `pack.json` must match as JSON.

A pass on a `pack-*` branch here then asks **Manifest** to run.

## The manifest (for maintainers)

**Manifest** (`.github/workflows/manifest.yml` on `master`) runs when a pack branch's check passes,
every six hours, and by hand. `scripts/Build-Manifest.ps1` lists each `pack-<id>` branch at its
current commit, and the result is committed to the `manifest` branch when it changed.

The plugin reads it from
`https://raw.githubusercontent.com/AJD-/custom-model-hub/manifest/manifest.json`, and each pack's
files from `.../<commit>/bundle.dat` and `.../<commit>/icon.png`. It's an array of entries:

```json
[
  {
    "id": "my-mole",
    "name": "My mole",
    "author": "You",
    "description": "A Giant Mole in a party hat.",
    "version": "1.0",
    "license": "CC-BY-4.0",
    "tags": ["moles"],
    "formatVersion": 3,
    "commit": "<40-character commit hash of the pack branch>",
    "size": 13589,
    "sha256": "<SHA-256 of bundle.dat, lowercase hex>",
    "hasIcon": true,
    "repo": "https://github.com/AJD-/custom-model-hub/blob/pack-my-mole/ABOUT.md",
    "models": [{ "key": 1005779, "name": "Giant Mole", "npcIds": [5779] }]
  }
]
```

`formatVersion` is read from the bundle's header. The plugin lists a pack built for another format
without letting it be installed.

When the tools or the bundle format change, move `TOOLS_REF` in `pack-empty`'s
`.github/workflows/check-pack.yml` on, and on every pack branch, then rebuild the packs it affects.

## License

The workflows and scripts here are BSD 2-Clause (see [LICENSE](LICENSE)). Each pack has its own
license, on its own branch.
