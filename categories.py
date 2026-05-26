"""Category constants and helper functions for DD Manager."""

import html
import os
import re

CATEGORY_COLORS = {
    "UI": "#8FA6B8",
    "Districts": "#6D9C9A",
    "Dungeons": "#B88B4A",
    "Quirks": "#B26B7B",
    "Trinkets": "#C1A85D",
    "Enemies": "#B65A4D",
    "Class Patch": "#879B5B",
    "Class": "#A4B56C",
    "Skins": "#9D7A9A",
    "Unassigned": "#82786B",
}

CATEGORY_COLOR_CYCLE = [
    "#5F8B7E",
    "#A66A4A",
    "#7D8FB3",
    "#A46D8A",
    "#9F9153",
    "#5E7A52",
    "#B46A5B",
    "#6E8C9C",
]

DEFAULT_CATEGORIES = [
    "UI",
    "Districts",
    "Dungeons",
    "Quirks",
    "Trinkets",
    "Enemies",
    "Class Patch",
    "Class",
    "Skins",
]


def get_categories(state):
    """Combine ordered, custom, and discovered categories without duplicates."""
    categories = []
    seen = set()

    for cat in state.get("category_order", []):
        if cat and cat not in ("All", "Unassigned") and cat.lower() not in seen:
            categories.append(cat)
            seen.add(cat.lower())

    for cat in state.get("custom_categories", []):
        if cat and cat.lower() not in seen and cat not in ("All", "Unassigned"):
            categories.append(cat)
            seen.add(cat.lower())

    for cat in state.get("categories", {}).values():
        if cat and cat.lower() not in seen and cat not in ("All", "Unassigned"):
            categories.append(cat)
            seen.add(cat.lower())

    return categories


def get_category_priority(state, base_priority, fallback=700):
    """Build sort buckets that respect the saved category order first."""
    categories = get_categories(state)
    priority = {
        cat: index * 100
        for index, cat in enumerate(categories)
    }

    for cat, value in base_priority.items():
        priority.setdefault(cat, value)

    priority.setdefault("Unassigned", fallback)
    return priority


def category_color(state, category, normalize_hex_color, fallback_text_color):
    """Resolve custom category colors, then built-in colors, then fallback."""
    saved = state.get("category_colors", {})
    custom = normalize_hex_color(saved.get(category, ""))
    if custom:
        return custom
    return CATEGORY_COLORS.get(category, fallback_text_color)


def default_color_for_new_category(state, normalize_hex_color, fallback_text_color):
    """Pick the first unused color from the category cycle."""
    used = {
        normalize_hex_color(color)
        for color in state.get("category_colors", {}).values()
        if normalize_hex_color(color)
    }
    for color in CATEGORY_COLOR_CYCLE:
        normalized = normalize_hex_color(color)
        if normalized and normalized not in used:
            return normalized
    return normalize_hex_color(CATEGORY_COLOR_CYCLE[0]) or fallback_text_color


def project_tag_values(mod_folder_path, mod, parse_xml_file_forgiving):
    """Read tag-like values from a mod's project.xml."""
    project_path = os.path.join(mod_folder_path(mod), "project.xml")
    if not os.path.exists(project_path):
        return []

    root = parse_xml_file_forgiving(project_path)
    if root is None:
        return []

    values = []
    seen = set()
    for elem in root.iter():
        if elem.tag.split("}", 1)[-1].lower() != "tags":
            continue

        text = re.sub(r"\s+", " ", "".join(elem.itertext())).strip()
        if not text:
            continue

        for part in re.split(r"[,/|]| {2,}", text):
            cleaned = html.unescape(part).strip()
            if cleaned and cleaned.lower() not in seen:
                values.append(cleaned)
                seen.add(cleaned.lower())

    return values


def auto_category_scores(state, mod, mod_folder_path, save_name, display_name, parse_xml_file_forgiving):
    """Score a mod against built-in categories using tags, paths, and names."""
    scores = {cat: 0 for cat in DEFAULT_CATEGORIES}
    mod_path = mod_folder_path(mod)
    title_bits = " ".join([
        mod,
        save_name(mod),
        display_name(mod),
        state.get("metadata", {}).get(mod, {}).get("title", ""),
    ]).lower()
    raw_tags = project_tag_values(mod_folder_path, mod, parse_xml_file_forgiving)
    tags = [tag.lower() for tag in raw_tags]

    ignore_tags = {
        "english", "korean", "japanese", "chinese", "russian",
        "spanish", "german", "french", "italian", "polish",
        "pets compatible", "com", "cc", "bc", "s-purple",
    }

    tag_rules = [
        ("UI", {"ui", "interface", "tooltip", "tooltips", "qol", "quality of life", "character_ui"}),
        ("Districts", {"district", "districts", "new district"}),
        ("Dungeons", {"dungeon", "dungeons", "new dungeon", "farmstead", "courtyard", "quest", "butcher's circus", "butchers circus"}),
        ("Quirks", {"quirk", "quirks", "disease", "diseases"}),
        ("Trinkets", {"trinket", "trinkets", "new trinkets"}),
        ("Enemies", {"monster", "monster mod", "monsters", "enemy", "enemies", "boss", "bosses", "new monsters", "new boss", "modded boss", "roaming boss"}),
        ("Class Patch", {"class tweaks", "patch", "compatibility", "rework"}),
        ("Class", {"class", "new class", "class mod", "character mod", "hero", "heroes"}),
        ("Skins", {"skin", "skins", "spriteset", "sprite", "reskin"}),
    ]

    for tag in tags:
        if tag in ignore_tags:
            continue
        for category, keywords in tag_rules:
            if tag in keywords:
                scores[category] += 4

    if os.path.isdir(mod_path):
        def has_dir(name):
            return os.path.isdir(os.path.join(mod_path, name))

        if has_dir("trinkets"):
            scores["Trinkets"] += 4
        if has_dir("monsters"):
            scores["Enemies"] += 6
        if has_dir("dungeons"):
            scores["Dungeons"] += 5
        if has_dir("quirks") or has_dir("diseases"):
            scores["Quirks"] += 5
        if has_dir("upgrades") and any("district" in tag for tag in tags):
            scores["Districts"] += 5
        if any(has_dir(name) for name in ("panels", "overlays", "fe_flow", "cursors", "scrolls")):
            scores["UI"] += 4
        if has_dir("heroes"):
            tag_blob = " ".join(tags)
            title_patch_words = (
                "patch", "addon", "add-on", "compatibility",
                "rebalance", "rework", "fix", "fixes", "tweak", "tweaks"
            )
            title_has_patch_words = any(word in title_bits for word in title_patch_words)
            has_class_identity = any(word in tag_blob for word in ("new class", "class mod", "character mod", " class "))
            hero_children = []
            try:
                hero_children = [
                    name for name in os.listdir(os.path.join(mod_path, "heroes"))
                    if os.path.isdir(os.path.join(mod_path, "heroes", name))
                ]
            except Exception:
                hero_children = []

            if any(word in tag_blob for word in ("skin", "skins", "sprite", "spriteset", "reskin")):
                scores["Skins"] += 7
            elif has_class_identity and hero_children and not title_has_patch_words:
                scores["Class"] += 8
            elif "class tweaks" in tag_blob and not has_class_identity:
                scores["Class Patch"] += 7
            elif title_has_patch_words:
                scores["Class Patch"] += 6
            elif hero_children:
                scores["Class"] += 6

    if "tooltip" in title_bits or "ui" in title_bits:
        scores["UI"] += 5
    if "character_ui" in title_bits:
        scores["UI"] += 6
    if "roster" in title_bits or "stack" in title_bits or "size" in title_bits:
        scores["UI"] += 5
    if "skin" in title_bits or "sprite" in title_bits:
        scores["Skins"] += 2
    if "district" in title_bits:
        scores["Districts"] += 5
    if "dungeon" in title_bits or "quest" in title_bits or "butcher" in title_bits or "circus" in title_bits:
        scores["Dungeons"] += 3
    if "trinket" in title_bits:
        scores["Trinkets"] += 2
    if "quirk" in title_bits or "quirks" in title_bits:
        scores["Quirks"] += 6
    if "vermintide" in title_bits:
        scores["Dungeons"] += 6
    if "smouldering ruin" in title_bits or "smoldering ruin" in title_bits or "kraken society" in title_bits:
        scores["Districts"] += 6
    if "monster mod" in title_bits:
        scores["Enemies"] += 6

    return scores


def suggested_category_for_mod(state, mod, mod_folder_path, save_name, display_name, parse_xml_file_forgiving):
    """Suggest one built-in category when heuristics produce a strong signal."""
    scores = auto_category_scores(
        state,
        mod,
        mod_folder_path,
        save_name,
        display_name,
        parse_xml_file_forgiving,
    )
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_category, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if best_score < 4:
        return None
    if best_category == "Dungeons" and best_score >= second_score:
        return best_category
    if best_category == "Class" and best_score > second_score:
        return best_category
    if best_score - second_score < 2:
        return None
    return best_category


def auto_categorize_mods(state, target_mods, suggested_category_for_mod, remember_mod_category, include_already_attempted=True):
    """Apply category suggestions to target mods and return changed/ambiguous lists."""
    attempted = state.setdefault("auto_category_attempted", {})
    changed = []
    ambiguous = []

    for mod in target_mods:
        current = state.get("categories", {}).get(mod, "")
        if current and current not in ("", "Unassigned", "All"):
            continue
        if not include_already_attempted and attempted.get(mod):
            continue

        suggestion = suggested_category_for_mod(mod)
        attempted[mod] = True
        if suggestion:
            state["categories"][mod] = suggestion
            remember_mod_category(mod, suggestion)
            changed.append((mod, suggestion))
        else:
            ambiguous.append(mod)

    return changed, ambiguous


def move_category(categories, index, delta):
    """Move a category up or down within the ordered category list."""
    if index is None or not (0 <= index < len(categories)):
        return None
    new_index = index + delta
    if not (0 <= new_index < len(categories)):
        return None
    categories[index], categories[new_index] = categories[new_index], categories[index]
    return new_index


def add_custom_category(categories, custom_categories, category_colors, name, chosen_color):
    """Append a new custom category and assign its chosen/default color."""
    categories.append(name)
    custom_categories.add(name)
    category_colors[name] = chosen_color
    return len(categories) - 1


def rename_custom_category(categories, custom_categories, category_colors, renamed_categories, index, old_name, new_name):
    """Rename a custom category and keep rename/color bookkeeping in sync."""
    categories[index] = new_name
    custom_categories.remove(old_name)
    custom_categories.add(new_name)
    if old_name in category_colors:
        category_colors[new_name] = category_colors.pop(old_name)
    original_name = renamed_categories.pop(old_name, old_name)
    renamed_categories[new_name] = original_name


def remove_custom_category(categories, custom_categories, category_colors, index, category_name):
    """Remove a custom category and return the next selected index."""
    categories.pop(index)
    custom_categories.remove(category_name)
    category_colors.pop(category_name, None)
    return min(index, len(categories) - 1) if categories else None


def apply_category_editor_changes(state, categories, category_colors, renamed_categories, normalize_hex_color):
    """Apply edited category ordering, renames, removals, and color settings to state."""
    final_categories = list(categories)
    final_custom = [cat for cat in final_categories if cat not in DEFAULT_CATEGORIES]

    removed_custom = [cat for cat in state.get("custom_categories", []) if cat not in final_custom]
    renamed_pairs = [
        (old_cat, new_cat)
        for new_cat, old_cat in renamed_categories.items()
        if old_cat != new_cat
    ]

    for old_cat, new_cat in renamed_pairs:
        for mod, category in list(state.get("categories", {}).items()):
            if category == old_cat:
                state["categories"][mod] = new_cat
        memory = state.get("category_memory", {})
        for key, category in list(memory.items()):
            if category == old_cat:
                memory[key] = new_cat

    for removed_cat in removed_custom:
        if removed_cat in renamed_categories.values():
            continue
        for mod, category in list(state.get("categories", {}).items()):
            if category == removed_cat:
                state["categories"].pop(mod, None)
        memory = state.get("category_memory", {})
        for key, category in list(memory.items()):
            if category == removed_cat:
                memory.pop(key, None)

    state["custom_categories"] = final_custom
    state["category_order"] = final_categories
    state["category_colors"] = {
        cat: normalize_hex_color(category_colors.get(cat, ""))
        for cat in final_categories
        if normalize_hex_color(category_colors.get(cat, ""))
    }

    return final_categories
