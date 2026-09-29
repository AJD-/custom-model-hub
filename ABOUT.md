# Arachnophobia

Replaces spiders with crabs, for players who would rather not look at spiders. Each crab is recolored
to match the spider it replaces, so spiders that differ by color still do: Sarachnis's melee spawn is
an orange crab, and her mage spawn a blue one.

| Spider | NPC ids | Crab |
|---|---|---|
| Giant spider | 3017, 3018 | amber-brown |
| Giant spider | 2477 | red-brown |
| Deadly red spider | 3021 | red and black |
| Jungle spider | 3020, 6267, 6271 | green |
| Temple Spider | 8703 | purple and red |
| Sarachnis | 8713 | dark red |
| Spawn of Sarachnis (melee) | 8714 | orange |
| Spawn of Sarachnis (mage) | 8715 | blue |

Each crab is sized to the spider's footprint. Clickboxes are the spider's own, and every spider
animation plays a crab animation of the same length: idle and walk loop the crab's, attacks and
blocks are stretched to fit, and deaths play at the crab's own pace. Sarachnis's melee and ranged
attacks both play the crab's one attack.

## What it's made from

The crab is the game's own **Crab (NPC 4822)**, exported from the game cache with `exportGltf`. Its
animations were put on the spiders' sequences with `retargetGltf`, using `source/crab.retarget.json`,
and `source/models.json` sets each spider's scale and recolor. `notes/` holds the script the recolors
were derived from, and a render of each crab beside its spider.

To rebuild, from the Custom NPC Models source folder, with `<pack>` the path to this pack:

```
./gradlew retargetGltf -Pglb=<pack>/source/crab.glb -Pmap=<pack>/source/crab.retarget.json -Pout=<pack>/source/crab-retargeted.glb
./gradlew generateAssets -PassetsDir=<pack>/source -PpackOut=<pack>
```

## License

The custom assets are BSD 2-Clause; the Jagex assets are excluded. See [LICENSE](LICENSE).

This is not affiliated with, authorized, maintained, or endorsed by Jagex. Old School RuneScape and
all associated visual assets, trademarks, and copyrights are the sole property of Jagex.
