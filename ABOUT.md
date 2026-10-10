# Zanik Thralls

Turns your Arceuus thralls into Zanik, the Dorgeshuun cave goblin, in three of her looks.

| Thrall | NPC ids | Becomes |
|---|---|---|
| Ghostly (Magic) | 10878, 10879, 10880 | Zanik in her HAM robes |
| Skeletal (Ranged) | 10881, 10882, 10883 | Zanik with her bone crossbow |
| Zombified (Melee) | 10884, 10885, 10886 | Zanik in Dorgesh-Kaan clothes, with a bone dagger |

Each thrall type is a model of its own in the side panel, and the lesser, superior and greater
thralls of a type look the same. All keep their size and clickbox. The spells' graphics, the
projectiles and the hit splats are unchanged.

When summoned, Zanik gets up off the ground in place of the thrall rising. She then idles, follows
you and attacks as the thrall does: the ghostly thrall points as it casts, the skeletal thrall
fires its crossbow, and the zombified thrall swings its dagger. A thrall leaves as it always does.

## What it's made from

The bodies, colors and animations are the game's own **Zanik**, exported from the game cache with
`exportGltf`:

- the HAM robes from NPC 4326
- the crossbow from NPC 4511
- the Dorgesh-Kaan clothes from NPC 2318, with the bone dagger from NPC 5140

Her idle (6040), walk (6041), getting up off a train track (6212) and attacks (pointing 5992, firing
her crossbow 5998, a Dorgeshuun club swing 6007) were put on the thralls' sequences with
`retargetGltf`, using `source/zanik-*.retarget.json`.

## License

The custom assets are BSD 2-Clause; the Jagex assets are excluded. See [LICENSE](LICENSE).

This is not affiliated with, authorized, maintained, or endorsed by Jagex. Old School RuneScape and
all associated visual assets, trademarks, and copyrights are the sole property of Jagex.
