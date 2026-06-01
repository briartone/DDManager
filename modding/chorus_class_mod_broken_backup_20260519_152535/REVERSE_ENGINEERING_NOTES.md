# Reverse Engineering Notes

These notes summarize the real mod structure I inspected while building this starter.

## Reference: The Powder Keg Class Mod

Observed at:

`C:\Program Files (x86)\Steam\steamapps\workshop\content\262060\2248772895`

Key structure:

- `project.xml`
- `heroes/keg_hunter/keg_hunter.info.darkest`
- `heroes/keg_hunter/keg_hunter.art.darkest`
- `effects/keg_hunter.effects.darkest`
- `localization/*.loc2`
- `localization/keg_hunter.string_table.xml`
- `trinkets/`
- `audio/`, `campaign/`, `raid/`, `shared/`, `upgrades/`

## Practical Takeaways

- `project.xml` carries workshop metadata plus title/tags.
- `*.info.darkest` is where base stats, weapons, armour, resistances, combat skills, move skill, and generation data live.
- `*.art.darkest` maps skill ids to icons, animations, and fx names.
- `effects/*.effects.darkest` is where heals, buffs, stuns, dots, and triggered effects are actually defined.
- `localization/*.string_table.xml` holds class name, skill names, upgrade labels, weapon names, armour names, and barks.

## How This Informs The Chorus

The hive-link concept maps best to:

- ally-target buffs in `effects`
- rank-restricted combat skills in `info.darkest`
- clear support skill naming in localization

## Constraint To Keep In Mind

A true persistent "linked ally" mechanic with lots of custom branching may need more advanced tricks than plain skill data supports comfortably.

For a first playable version, the cleanest route is:

- one ally-buff skill that establishes the host
- several support skills that are just strong when used from back ranks
- a weak self-preservation package when displaced forward
