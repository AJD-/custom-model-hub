# Maid Yama

Dresses Yama, his pet Yami, and Yama on his throne as a maid. He wears a black bodice with a
ruffled sweetheart neckline and a small bow, a white collar and black bow tie, puffed sleeves and a
frilled headband. Over the skirt go a frilled apron, a ruffled petticoat and a bow at the back, with
frilled garters and bows on his bare thighs. His staff, wings, horns, mane and flame are his own.

| NPC | NPC ids | Scale |
|---|---|---|
| Yama | 14176 | 160 |
| Yami | 14203, 14204 | 30 |
| Yama on his throne | 124 | 128 |

Each is a model of its own in the side panel. In dialogue, Yama on his throne's head wears the
headband too. The scales, lighting and clickboxes are the game's own. Every animation is Yama's
own, on his own skeleton: standing, walking, his attacks and his death, and his idle on the throne.
The skirt follows his legs through all of them.

## What it's made from

Yama's animations are skeletal ones, which Custom NPC Models' authoring tools read from the game
cache since the skeletal support on the `feature/skeletal-anims` branch. The body, wings, staff,
skeleton and animations are the game's own **Yama (NPC 14176)**, and for the throne **NPC 124**,
exported from the game cache with `exportGltf` into `export/`. `notes/build_yamamaid.py` dresses
him in Blender 5.2:

- His chest becomes the bodice, black below the neckline and bare above it, with a modest bust. His
  thighs are bare red skin, their fur tufts pulled in smooth.
- Everything else is new geometry at the game's low-poly density, fitted to him by ray-cast and
  weighted to his bones. That covers the skirt and everything on it, the neckline ruffle, collar,
  bow tie, sleeves, garters and headband.
- The skirt rides joints of its own, keyed through every animation, which turn about his hips with
  his thighs:
  - lower on the skirt they follow his thighs further;
  - each side follows whichever knee reaches further its way, so the front follows the leading
    thigh, the back the trailing one, and the sides whichever splays out;
  - on the throne his thighs carry the front and sides as his lap, and the back stays on the seat.
- His dialogue head is the game's own chathead for NPC 124, which the dialogue's NPC 123 turns
  into, with the headband fitted between its horns. Its emotes are the game's own.
- Yami is Yama's own geometry at pet size, without the boss's flame. Yama on his throne is an older,
  smaller model: the same outfit is fitted to him by the same script, its heights mapped about his
  hips and its sizes scaled to him.

`notes/render_yamamaid.py` renders `notes/preview.png` and `icon.png`. The preview shows him
standing from four sides, close-ups, and frames of the idle and the walk. `notes/preview-throne.png`
shows him on the throne. Other scripts were used to fit and check him:

- `notes/clips_yamamaid.py` renders strips of every clip, or one frame from four sides.
- `notes/poke_yamamaid.py` counts, frame by frame, legs passing out through the skirt and his staff
  passing in.
- `notes/closeup_yamamaid.py` renders close views, posed or at rest.
- `notes/probe_yamamaid.py` and `notes/sections_yamamaid.py` list an export's parts, bones, colors
  and cross-sections.

To rebuild, with `<pack>` the path to this pack: from the Custom NPC Models source folder, on a
build with skeletal support, export Yama and Yama on his throne,

```
./gradlew exportGltf -Pnpc=14176 -Pout=<pack>/export/14176
./gradlew exportGltf -Pnpc=124 -Pseqs=12153 -Pout=<pack>/export/124
./gradlew exportGltf -Pnpc=124 -Pchathead -Pout=<pack>/export/chathead-124
```

then, in Blender,

```
blender -b --factory-startup -P <pack>/notes/build_yamamaid.py
blender -b --factory-startup -P <pack>/notes/build_yamamaid.py -- throne
blender -b --factory-startup -P <pack>/notes/build_yamamaid.py -- chathead
blender -b --factory-startup -P <pack>/notes/render_yamamaid.py -- <pack>/source/yama-maid.glb <pack>/notes/preview.png <pack>/icon.png
```

and back in the Custom NPC Models folder:

```
./gradlew generateAssets -PassetsDir=<pack>/source -PpackOut=<pack>
```

## License

The custom assets are BSD 2-Clause; the Jagex assets are excluded. See [LICENSE](LICENSE).

This is not affiliated with, authorized, maintained, or endorsed by Jagex. Old School RuneScape and
all associated visual assets, trademarks, and copyrights are the sole property of Jagex.
