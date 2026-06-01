# Chorus Class Mod Starter

This is a starter scaffold for a new Darkest Dungeon class mod built around your concept:

- A hive-mind themed support class
- Stronger support tools in ranks 3-4
- Noticeably worse when trapped in rank 1
- No true guard tank role; survives through positioning, buffs, and link utility instead

## Working Name

- Class display name: `The Chorus`
- Internal hero id: `chorus`

## What Is Included

- `project.xml`
- `heroes/chorus/chorus.info.darkest`
- `heroes/chorus/chorus.art.darkest`
- `effects/chorus.effects.darkest`
- `localization/chorus.string_table.xml`
- `modfiles.txt`
- `REVERSE_ENGINEERING_NOTES.md`

## What This Starter Is

This is a clean editable template, not a finished drop-in release. It gives us:

- a file layout that matches real class mods
- placeholder combat skills and effects
- localization keys in the format existing mods use
- a first pass at the "position changes role" concept through rank-locked skills

## Important Design Note

Darkest Dungeon class data supports "usable from these ranks" very naturally, but does not make true "this skill changes because I am in rank 2 instead of 4" especially easy in plain data files.

So this starter expresses your idea like this:

- front ranks: weak emergency actions and reposition tools
- middle ranks: mixed link and utility actions
- back ranks: strongest support, healing, and party-buff access

That gives the class a real positional identity without pretending the engine has a richer conditional system than it does.

## First-Pass Combat Kit

1. `sting_order`
   Rank 1-3 fallback attack that nudges the Chorus backward and gives a tiny self-dodge bump.
2. `host_designation`
   Rank 2-4 ally designation skill. Buffs the chosen ally and gives the Chorus a smaller mirrored benefit.
3. `shared_vitality`
   Rank 3-4 direct ally heal with minor self stress relief.
4. `chorus_hymn`
   Rank 3-4 party support song with accuracy/speed support and light stress relief for allies.
5. `relay_impulse`
   Rank 1-2 emergency reposition to retreat from the front and regain support posture.
6. `neural_static`
   Rank 3-4 rear control tool that applies speed and attack debuffs.
7. `swarm_surge`
   Rank 1-2 emergency self-preservation action with healing, dodge, and stress relief.

## Recommended Next Steps

1. Replace placeholder balance numbers with a real progression pass.
2. Decide whether the "host" mechanic should stay as a short-duration buff or become a more advanced custom state.
3. Tune the class identity harder toward one of these:
   healing anchor,
   momentum support,
   or debuff conductor.
4. Add art, animation, icons, camping skills, trinkets, and proper tooltip/localization coverage.

## Install Path

This scaffold was created in the workspace on purpose so we can iterate safely.

When you want to test it in-game, copy the `chorus_class_mod` folder contents into a real Darkest Dungeon mod folder, usually:

`DarkestDungeon\\mods\\your_mod_folder_name`

## References Used

- `The Powder Keg Class Mod` for overall folder layout and file naming
- existing class-mod conventions visible in your current mod library
