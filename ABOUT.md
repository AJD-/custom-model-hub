# Mortina Maid

Turns your house servants into Mortina Daubenton, a vampyre of Darkmeyer.

| Servant | NPC ids |
|---|---|
| Maid | 223, 7328 |
| Demon butler | 229, 7331 |

Each servant is a model of its own in the side panel. Both keep their size and clickbox.

Her idle loops over the servants' standing sequence, and her walk over their walking and turning
sequences.

In dialogue, both servants show Mortina's own chathead, with whatever emote the game calls for.

## What it's made from

The body, colors, idle and walk are **Mortina Daubenton (NPC 9708)**, exported from
the game cache with `exportGltf`. Her idle and walk were put on the servants' sequences with
`retargetGltf`, using `source/mortina.retarget.json`. Her chathead is borrowed from the game, not
shipped in the pack.

## License

The custom assets are BSD 2-Clause; the Jagex assets are excluded. See [LICENSE](LICENSE).

This is not affiliated with, authorized, maintained, or endorsed by Jagex. Old School RuneScape and
all associated visual assets, trademarks, and copyrights are the sole property of Jagex.
