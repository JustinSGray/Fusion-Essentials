# Copyright (c) Fusion-Essentials contributors
# Dual-licensed under the MIT and Apache-2.0 licenses; see LICENSE-MIT and LICENSE-APACHE.

"""Add, update, delete, hide or show rows of a sheet's one revision table (Sheet.addRevisionTable
allows exactly one per sheet). deleteRow and updateRevisionRow on the title and header rows return
true and change nothing, so every write is judged by the row census. WRITES (destructive: delete)."""

import adsk.core
import adsk.drawing

from ..mcp_primitives.tool import Tool
from ..mcp_primitives.item import Item, Verification
from ..mcp_primitives.registry import register
from ._common import error, ok, safe
from . import _common
from . import _drawing_common
from . import _inputs
from . import _outputs

RETURNS = [
    _outputs.ReturnsValue("revision_count_after", "the revision table's row census length after "
                          "the call"),
]

_ACTIONS = ("add", "update", "delete", "hide", "show")
_ACTION_INPUTS = {"add": ("rows",), "update": ("row", "index"), "delete": ("index",),
                  "hide": ("index",), "show": ("index",)}
_ACTION = _inputs.Choice("action", list(_ACTIONS), required=True)

_TEXT_FIELDS = ("rev", "description", "date", "approved", "zone")
_ROW_FORM = "|".join(_TEXT_FIELDS)
_HEADER_ROWS = 2       # rows 0 (title) and 1 (header); a false-success zone on update/delete

_NOTE = ("The table sits in the sheet's top-right corner; no API moves or deletes it. "
        "drawing_export's PDF shows it, doc_save persists the drawing.")


def _row_texts(raw, label):
    """(the five texts as a dict, error) for one 'rev|description|date|approved|zone' string."""
    if not isinstance(raw, str):
        return None, f"{label} must be a '{_ROW_FORM}' string (got {raw!r})."
    fields = [f.strip() for f in raw.split("|")]
    if len(fields) > len(_TEXT_FIELDS):
        return None, (f"{label} {raw!r} has {len(fields)} '|'-separated fields; '{_ROW_FORM}' "
                      f"takes at most {len(_TEXT_FIELDS)}.")
    if not fields[0]:
        return None, f"{label} {raw!r} needs a non-empty 'rev', such as 'A|Initial release'."
    fields += [""] * (len(_TEXT_FIELDS) - len(fields))
    return dict(zip(_TEXT_FIELDS, fields)), None


def _row_index(raw, count):
    """(index, error) - a table row index within [0, count), as the census lists it."""
    idx = _drawing_common.as_index(raw)
    if isinstance(idx, bool) or not isinstance(idx, int):
        return None, f"'index' must be an integer row index (got {raw!r})."
    if not 0 <= idx < count:
        span = f"0 to {count - 1}" if count else "none"
        return None, f"'index' {idx} is out of range: the table holds {count} row(s) ({span})."
    return idx, None


def _new_row(texts):
    """A RevisionTableRow.create() with `texts` set, or None when the factory answers nothing."""
    r = safe(lambda: adsk.drawing.RevisionTableRow.create())
    if r is None:
        return None
    for field, value in texts.items():
        setattr(r, field, value)
    return r


def _fields_match(requested, got):
    """True when every non-empty requested text reads back - Fusion leaves a cell sent empty unchanged."""
    return all(got.get(f) == v for f, v in requested.items() if v)


def _stripped(row):
    """`row` without its position-derived index - the shape a before/after census compares."""
    return {k: v for k, v in row.items() if k != "index"}


def _title_header_clause(idx):
    """The clause a false-success names when `idx` is the title (0) or header (1) row, else ''."""
    return f" - row {idx} is the table's title/header row." if idx < _HEADER_ROWS else "."


def _get_table(sheet):
    """(table, error) - Sheet.getRevisionTable(), a raise reported distinctly from 'no table'."""
    try:
        return sheet.getRevisionTable(), None
    except Exception as ex:
        return None, error(f"Sheet.getRevisionTable() raised: {ex}.")


def _do_add(sheet, raw_rows):
    """add: create the table when the sheet holds none, else append via addRevision per row."""
    listed = _drawing_common.listed(raw_rows)
    if not isinstance(listed, (list, tuple)) or not listed:
        return error(f"action='add' needs 'rows' as one or more '{_ROW_FORM}' strings "
                     f"(got {raw_rows!r}).")
    parsed = []
    for i, text in enumerate(listed):
        texts, err = _row_texts(text, f"rows[{i}]")
        if err:
            return error(err)
        parsed.append(texts)

    name = safe(lambda: sheet.name)
    table, terr = _get_table(sheet)
    if terr:
        return terr

    if table is None:
        n_before = 0
    else:
        before = _drawing_common.revision_rows(table)
        if before is None:
            return error("The existing revision table's rows did not read - refusing to add "
                         "without a reliable census.")
        n_before = len(before)

    if table is None:
        inp = safe(lambda: sheet.revisionTableInput())
        if inp is None:
            return error(f"Sheet.revisionTableInput() did not read on '{name}' - nothing was added.")
        made_rows = []
        for i, texts in enumerate(parsed):
            r = _new_row(texts)
            if r is None:
                return error(f"RevisionTableRow.create() returned nothing for rows[{i}] - "
                             "nothing was added.")
            made_rows.append(r)
        try:
            inp.revisionTableRows = made_rows
            inp.doAutoPopulateSheet = True
        except Exception as ex:
            return error(f"Could not configure the revision table input: {ex}. Nothing was added.")
        try:
            new_table = sheet.addRevisionTable(inp)
        except Exception as ex:
            return error(f"Sheet.addRevisionTable raised: {ex}. Nothing was added.")
        if new_table is None:
            return error("Sheet.addRevisionTable returned nothing - no revision table was added.")
        table = new_table
        table_created = True
    else:
        table_created = False
        for i, texts in enumerate(parsed):
            try:
                r = _new_row(texts)
                landed = False if r is None else table.addRevision(r)
            except Exception as ex:
                now = _drawing_common.revision_rows(table)
                return error(f"addRevision raised on rows[{i}]: {ex}. The table now reads {now}.")
            if r is None:
                now = _drawing_common.revision_rows(table)
                return error(f"RevisionTableRow.create() returned nothing for rows[{i}] - the "
                             f"table now reads {now}.")
            if not landed:
                now = _drawing_common.revision_rows(table)
                return error(f"addRevision refused rows[{i}] ({listed[i]!r}); the table now "
                             f"reads {now}.")

    after = _drawing_common.revision_rows(table)
    if after is None:
        return error(f"The revision table's rows did not read back after the add "
                     f"(table_created={table_created}) - unverified.")
    if table_created:
        bad = len(after) != len(parsed) + _HEADER_ROWS
    else:
        bad = len(after) - n_before != len(parsed)
    tail = after[-len(parsed):] if len(after) >= len(parsed) else []
    bad = bad or len(tail) != len(parsed) or any(
        not _fields_match(texts, got) for texts, got in zip(parsed, tail))
    if bad:
        return error(f"The revision table (table_created={table_created}) reads {len(after)} "
                     f"row(s) ({n_before} before) - the requested row(s) do not read back as "
                     f"asked: {after}.")
    return ok({
        "action": "add",
        "sheet": name,
        "table_created": table_created,
        "revision_count_before": n_before,
        "revision_count_after": len(after),
        "visible_count": _common.counted(lambda: table.rowCount),
        "rows": after,
        "note": _NOTE,
    })


def _do_update(sheet, table, before, row, index):
    """update: updateRevisionRow(index, row); judged by the census (title/header rows: false-success)."""
    if row is None:
        return error(f"action='update' needs 'row' - a '{_ROW_FORM}' string.")
    texts, err = _row_texts(row, "row")
    if err:
        return error(err)
    idx, err = _row_index(index, len(before))
    if err:
        return error(err)
    r = _new_row(texts)
    if r is None:
        return error("RevisionTableRow.create() returned nothing - nothing was updated.")
    try:
        landed = table.updateRevisionRow(idx, r)
    except Exception as ex:
        return error(f"updateRevisionRow raised on row {idx}: {ex}.")
    if not landed:
        return error(f"updateRevisionRow returned false for row {idx} - nothing changed.")
    after = _drawing_common.revision_rows(table)
    if after is None or not 0 <= idx < len(after):
        return error("The revision table's rows did not read back after the update - unverified.")
    got = after[idx]
    if not _fields_match(texts, got):
        return error(f"Fusion accepted the update but row {idx} still reads {got}"
                     f"{_title_header_clause(idx)}")
    return ok({
        "action": "update",
        "sheet": safe(lambda: sheet.name),
        "index": idx,
        "row": got,
        "revision_count_before": len(before),
        "revision_count_after": len(after),
        "visible_count": _common.counted(lambda: table.rowCount),
        "rows": after,
        "note": _NOTE,
    })


def _do_delete(sheet, table, before, index):
    """delete: deleteRow(index); judged by the whole census (title/header rows: false-success)."""
    idx, err = _row_index(index, len(before))
    if err:
        return error(err)
    before_row = before[idx]
    try:
        landed = table.deleteRow(idx)
    except Exception as ex:
        return error(f"deleteRow raised on row {idx}: {ex}.")
    if not landed:
        return error(f"deleteRow returned false for row {idx} - nothing changed.")
    after = _drawing_common.revision_rows(table)
    if after is None:
        return error(f"The revision table's rows did not read back after deleting row {idx} - "
                     "unverified.")
    after_stripped = [_stripped(r) for r in after]
    before_stripped = [_stripped(r) for r in before]
    expected = before_stripped[:idx] + before_stripped[idx + 1:]
    if after_stripped != expected:
        if after_stripped == before_stripped:
            shown = after[idx] if idx < len(after) else before_row
            return error(f"Fusion accepted the delete but row {idx} still reads {shown}"
                         f"{_title_header_clause(idx)}")
        return error(f"Fusion accepted the delete but the table reads {after} - expected row "
                     f"{idx} ({before_row}) removed and every other row unchanged.")
    return ok({
        "action": "delete",
        "sheet": safe(lambda: sheet.name),
        "index": idx,
        "before_row": before_row,
        "revision_count_before": len(before),
        "revision_count_after": len(after),
        "visible_count": _common.counted(lambda: table.rowCount),
        "rows": after,
        "note": _NOTE,
    })


def _do_visibility(sheet, table, before, index, want_visible):
    """hide/show: setRevisionVisibility(index, want_visible); a state already held mutates nothing."""
    idx, err = _row_index(index, len(before))
    if err:
        return error(err)
    action = "show" if want_visible else "hide"
    now = before[idx].get("visible")
    if now is want_visible:
        return ok({
            "action": action,
            "sheet": safe(lambda: sheet.name),
            "index": idx,
            "row": before[idx],
            "changed": False,
            "revision_count_before": len(before),
            "revision_count_after": len(before),
            "visible_count": _common.counted(lambda: table.rowCount),
            "rows": before,
            "note": f"Row {idx} already reads visible={want_visible} - nothing changed. " + _NOTE,
        })
    try:
        landed = table.setRevisionVisibility(idx, want_visible)
    except Exception as ex:
        return error(f"setRevisionVisibility raised on row {idx}: {ex}.")
    if not landed:
        return error(f"setRevisionVisibility returned false for row {idx} - nothing changed.")
    after = _drawing_common.revision_rows(table)
    got = after[idx].get("visible") if after is not None and idx < len(after) else None
    if got is not want_visible:
        return error(f"Fusion accepted the visibility change but row {idx} still reads "
                     f"visible={got}.")
    return ok({
        "action": action,
        "sheet": safe(lambda: sheet.name),
        "index": idx,
        "row": after[idx],
        "changed": True,
        "revision_count_before": len(before),
        "revision_count_after": len(after),
        "visible_count": _common.counted(lambda: table.rowCount),
        "rows": after,
        "note": _NOTE,
    })


def handler(action: str = "", sheet: str = "", rows=None, row: str = None, index=None) -> dict:
    """See TOOL_DESCRIPTION."""
    act, act_err = _ACTION.resolve(action)
    if act_err:
        return error(act_err)
    raw = {"rows": rows, "row": row, "index": index}
    stray = [n for n, v in raw.items() if v not in (None, "", []) and n not in _ACTION_INPUTS[act]]
    if stray:
        return error(f"action='{act}' reads {', '.join(_ACTION_INPUTS[act])} beside 'sheet' - it "
                     f"does not take {', '.join(stray)}.")

    dwg = _drawing_common.active_drawing()
    if dwg is None:
        return error("The active document is not a drawing, so it has no revision table. Open "
                     "the drawing (doc_open by file_id) and make it active, then retry.")
    target_sheet, serr = _drawing_common.resolve_sheet(dwg, (sheet or "").strip())
    if serr:
        return error(serr)

    if act == "add":
        return _do_add(target_sheet, rows)

    table, terr = _get_table(target_sheet)
    if terr:
        return terr
    if table is None:
        return error(f"Sheet '{safe(lambda: target_sheet.name)}' holds no revision table yet - "
                     "action='add' creates one.")
    census_before = _drawing_common.revision_rows(table)
    if census_before is None:
        return error("The revision table's rows did not read - nothing changed.")

    if act == "update":
        return _do_update(target_sheet, table, census_before, row, index)
    if act == "delete":
        return _do_delete(target_sheet, table, census_before, index)
    return _do_visibility(target_sheet, table, census_before, index, act == "show")


TOOL_DESCRIPTION = (
    "Add, update, delete, hide or show rows of a sheet's one revision table. 'rows'/'row' are "
    "'rev|description|date|approved|zone'. drawing_get(include=['revisions']) lists indexes; "
    "drawing_export shows the PDF."
)

FULL_DESCRIPTION = TOOL_DESCRIPTION + "\n" + _outputs.produces_block(RETURNS)

tool = (
    Tool.create_simple(name="drawing_edit_revisions", description=FULL_DESCRIPTION)
    .add_input_property(*_ACTION.as_property())
    .add_input_property("sheet", {"type": "string", "description": "Omit for the active sheet."})
    .add_input_property("rows", {"type": "array", "items": {"type": "string"},
            "description": "For add: one or more rows."})
    .add_input_property("row", {"type": "string", "description": "For update."})
    .add_input_property("index", {"type": "integer", "description": "For update/delete/hide/show."})
    .strict_schema()
)

item = Item.create_tool_item(
    tool=tool, write="destructive", handler=handler, run_on_main_thread=True,
    verification=Verification(
        kind="inline", rung="value",
        evidence_test="tests/unit/test_drawing_edit_revisions.py::TestDelete"
                      "::test_deleting_the_header_row_is_a_false_success"))


def register_tool():
    register(item)
