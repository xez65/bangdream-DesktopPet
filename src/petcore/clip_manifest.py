"""Single source of truth for the 17 clips shipped in the first pack.

``unity_index.json`` carries no usable ``loop`` flag (397/397 are false) and has no notion of
what a clip is *for*, so ``loop_mode`` and ``kind`` are editorial decisions recorded here.
Both the builder (``tools/build_clips.py``) and the runtime (``petcore.behavior``) read this
table, which is what stops the mapping in the design doc from drifting away from the pack.
"""

from __future__ import annotations

from dataclasses import dataclass

CHARACTER = "sakiko"
FALLBACK_SLUG = "sakiko_idle01"


@dataclass(frozen=True)
class ClipDef:
    slug: str
    label: str          # shown in the right-click menu
    kind: str           # primary role used by the behaviour machine
    loop_mode: str      # "loop" | "once"  (once = play through, then hand back to idle)
    pools: tuple        # behaviour pools this clip may be drawn from


CLIPS: tuple[ClipDef, ...] = (
    ClipDef("sakiko_idle01", "待机", "idle", "loop", ("idle",)),
    ClipDef("sakiko_nf_left01", "向左移动", "walk_left", "loop", ("walk",)),
    ClipDef("sakiko_nf_right01", "向右移动", "walk_right", "loop", ("walk",)),
    ClipDef("sakiko_surprised01", "被拎起", "held", "loop", ()),
    ClipDef("sakiko_odoodo01", "落地慌张", "land", "once", ("small",)),
    ClipDef("sakiko_smile01", "被戳开心", "react_poke", "once", ()),
    ClipDef("sakiko_smile03", "微笑", "small", "once", ("small",)),
    ClipDef("sakiko_angry01", "不满", "react_annoyed", "once", ()),
    ClipDef("sakiko_angry03", "生气", "react_angry", "once", ()),
    ClipDef("sakiko_nod01", "点头接受", "eat_yes", "once", ("small",)),
    ClipDef("sakiko_shame01", "害羞", "pet", "once", ()),
    ClipDef("sakiko_sad01", "难过", "hungry", "once", ("low",)),
    ClipDef("sakiko_cry01", "哭", "sad_low", "once", ("low",)),
    ClipDef("sakiko_thinking01", "思考陪读", "quiet", "loop", ("small",)),
    ClipDef("sakiko_serious01", "认真", "quiet_alt", "loop", ("small",)),
    ClipDef("sakiko_bye01", "打招呼", "greet", "once", ()),
    ClipDef("sakiko_sigh01", "叹气", "sedentary", "once", ("small",)),
)

_SLUGS = {c.slug for c in CLIPS}


def by_slug() -> dict[str, ClipDef]:
    return {c.slug: c for c in CLIPS}


def pool(name: str) -> tuple[str, ...]:
    return tuple(c.slug for c in CLIPS if name in c.pools)


# Named roles the behaviour machine plays. Every entry must exist in CLIPS.
IDLE = FALLBACK_SLUG
WALK_LEFT = "sakiko_nf_left01"
WALK_RIGHT = "sakiko_nf_right01"
HELD = "sakiko_surprised01"
LAND = "sakiko_odoodo01"
POKED = ("sakiko_smile01", "sakiko_smile03")
POKED_ANNOYED = ("sakiko_angry01", "sakiko_angry03")
PET = ("sakiko_nod01", "sakiko_shame01")
FEED = ("sakiko_nod01", "sakiko_shame01")
THROWN = (LAND,)
CHIME = ("sakiko_bye01",)
SEDENTARY = ("sakiko_sigh01",)
QUIET = ("sakiko_thinking01", "sakiko_serious01")
LOW_STATS = ("sakiko_sad01", "sakiko_cry01")
SMALL = pool("small")
MENU_ORDER = tuple(c.slug for c in CLIPS)
