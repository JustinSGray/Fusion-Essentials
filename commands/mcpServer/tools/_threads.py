# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Thread-table lookup shared by model_hole and model_thread."""

from difflib import SequenceMatcher

from ._common import safe

MAP_BLURB = ("resolve_thread_info - the ONE thread-table walk turning a bare designation "
             "('M5x0.8', '1/4-20 UNC') into a ThreadInfo, shared by model_hole's tap and "
             "model_thread; also returns every thread type carrying that designation")


def thread_types_for(tdq, designation, candidates=None):
    """Every thread type whose table carries `designation`, in library order."""
    hits = []
    for ttype in (safe(lambda: list(tdq.allThreadTypes), []) or []):
        for size in (safe(lambda t=ttype: list(tdq.allSizes(t)), []) or []):
            desigs = safe(lambda t=ttype, s=size: list(tdq.allDesignations(t, s)), []) or []
            if candidates is not None:
                candidates.extend((ttype, d) for d in desigs)
            if designation in desigs:
                hits.append(ttype)
                break
    return hits


def _nearby_choices(tdq, candidates, designation, internal, thread_type, thread_class):
    """Return bounded actual nearby spellings, preferring the supplied type and class."""
    ranked = sorted(dict.fromkeys(candidates),
                    key=lambda row: (SequenceMatcher(None, designation, row[1]).ratio(), row[1]),
                    reverse=True)
    matching, alternatives, class_cache = [], [], {}
    def classes_for(ttype, desig):
        key = (ttype, desig)
        if key not in class_cache and len(class_cache) < 20:
            class_cache[key] = safe(lambda: list(tdq.allClasses(internal, ttype, desig)), []) or []
        return class_cache.get(key, [])
    compatible_ranked = ([row for row in ranked if row[0].lower() == thread_type.lower()]
                         if thread_type else ranked)
    for ttype, desig in compatible_ranked[:10]:
        if SequenceMatcher(None, designation, desig).ratio() < 0.6:
            continue
        classes = classes_for(ttype, desig)
        compatible_classes = ([c for c in classes if c.lower() == thread_class.lower()]
                              if thread_class else classes)
        if compatible_classes:
            matching.append(f"'{desig}' in '{ttype}' (classes: {', '.join(compatible_classes[:3])})")
            if len(matching) == 5:
                break
    if matching:
        return "; ".join(matching)
    for ttype, desig in ranked[:10]:
        if SequenceMatcher(None, designation, desig).ratio() < 0.6:
            continue
        classes = classes_for(ttype, desig)
        if classes:
            alternatives.append(f"'{desig}' in '{ttype}' (classes: {', '.join(classes[:3])})")
            if len(alternatives) == 5:
                break
    return "; ".join(alternatives)


def resolve_thread_info(comp, designation, internal=True, thread_type="", thread_class=""):
    """Build a ThreadInfo for a thread DESIGNATION like 'M5x0.8'. `thread_type` picks the standard
    when several carry it, `thread_class` the fit within that standard.
    Returns (threadInfo, types_carrying_it, None) or (None, types, error)."""
    # An empty ThreadFeatures collection is falsy (count 0) but not None.
    tf = safe(lambda: comp.features.threadFeatures)
    if tf is None:
        return None, [], "This component has no thread features collection."
    tdq = safe(lambda: tf.threadDataQuery)
    if tdq is None:
        return None, [], "Thread data query unavailable."

    candidates = []
    hits = thread_types_for(tdq, designation, candidates)
    if not hits:
        choices = _nearby_choices(tdq, candidates, designation, internal,
                                  (thread_type or "").strip(), (thread_class or "").strip())
        remedy = (f"Nearby library spellings (not fit recommendations): {choices}. "
                  "Choose a listed designation, type and class, then retry; no selector was changed."
                  if choices else
                  "No nearby alternative with readable classes was found. "
                  "Check the designation, thread_type and thread_class in Fusion's Thread dialog.")
        return None, [], f"No thread designation '{designation}' found in the thread library. {remedy}"
    want = (thread_type or "").strip()
    if want:
        chosen = next((t for t in hits if t.lower() == want.lower()), None)
        if chosen is None:
            return None, hits, (f"Thread type '{thread_type}' does not carry '{designation}'. "
                                f"Types that do: {', '.join(hits)}.")
    else:
        # Types sharing a designation build ThreadInfos equal in every scalar but threadType, so
        # library order picks one; the caller is returned `hits` to see what else carried it.
        chosen = hits[0]

    # A class is a fit tolerance, not interchangeable: 4g6g and 6g are different fits of one thread.
    classes = safe(lambda: list(tdq.allClasses(internal, chosen, designation)), []) or []
    want = (thread_class or "").strip()
    if want:
        cls = next((c for c in classes if c.lower() == want.lower()), None)
        if cls is None:
            return None, hits, (f"Thread class '{thread_class}' is not offered for '{designation}' "
                                f"in '{chosen}'. Classes that are: {', '.join(classes) or '(none)'}.")
    else:
        cls = classes[0] if classes else ""
    ti = safe(lambda: tf.createThreadInfo(internal, chosen, designation, cls))
    if ti is None:
        return None, hits, f"createThreadInfo failed for '{designation}' in '{chosen}'."
    return ti, hits, None
