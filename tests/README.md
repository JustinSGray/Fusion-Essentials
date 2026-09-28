# Tests

Tests for the MCP tools in `commands/mcpServer/tools/`. They run **outside
Fusion** against a mocked `adsk` layer, so the whole suite finishes in seconds
and needs no live Fusion session.

The tree splits by what a test does:

- `tests/unit/` - tests that exercise behavior (per-tool handlers, the shared framework, the server).
- `tests/lints/` - tests that read the codebase to enforce a convention (naming, wire ASCII, dead
  code, doc freshness, ...). These are the repo policing itself.
- `tests/live/` - Fusion-driven scripts (`tool_verify.py`, `measure_api.py`, the cold-agent
  evals). Run them on demand with a real Fusion session; the mock suite does not collect them.
- `tests/fakes/` - the shared Fusion fakes, one module per family; `conftest.py` re-exports them.
- `tests/` root - the shared harness: `conftest.py` and the `gen_*.py` generators.

```bash
py -3 tests/check_all.py                     # run before calling a change done: generator checks + suite + live gate
py -3 tests/check_all.py --offline           # no Fusion here (skips the live gate, visibly)
py -3 -m pytest tests/unit/test_sys_get_selection.py -v   # one tool, verbose (while iterating)
py -3 tests/gen_all.py                       # regenerate the docs under tests/generated/
```

`check_all.py` runs everything in dependency order and, when a stage fails, prints the command that
repairs it. `py -3 tests/check_all.py --help` lists every stage.

A pass is either LIVE-VERIFIED (the stamp on the measured API facts was checked against a running
Fusion) or OFFLINE (you asked for it explicitly; the mocks were not re-confirmed). Either way it
checks the live-run receipt: `tests/live/VERIFIED_TOOLS.md` carries a source hash from the last green
`tool_verify.py` run, and `check_all.py` fails when tool source has changed since. To repair it,
re-run `tool_verify.py` with Fusion up (in one go, or in chunks with `--run <id>` / `--resume`) and
commit the rewritten receipt.

The receipt's count line splits `covered` (a step's predicate read a value off the payload) from
`called` (bare `ok` steps only: the call did not fail, but the effect was not read). The `called`
number is the queue of steps that still need an effect read.

> Requires `pytest` (`py -3 -m pip install pytest`). The live sheet-metal drawing check also
> requires `pypdf` (`py -3 -m pip install pypdf`). Config lives in `pytest.ini` at the repo root;
> it sets `testpaths`/`pythonpath`, so no environment variables are needed.

## What these test (and what they don't)

The tools are written for a *live* Fusion session, but most of their bugs live
in plain logic that runs before and around the Fusion calls: unit conversions,
string/path/URN parsing, the 0/1/N-item branches, entity classification, and
the `ok`/`error` result contract every tool returns. That logic breaks
**silently**: a wrong unit factor or a dropped error path returns subtly wrong
JSON to the agent, with no exception. That's what we pin down.

We **do not** unit-test tools whose only job is to forward data to or from the
Fusion API. Mocking `adsk` just to assert "it copied `app.version` into a
field" tests the mock, not the code. That belongs to the in-Fusion integration
layer (driven through the Fusion MCP server), not here. A tool module left
without a unit test needs an `UNTESTED` entry giving its Tier 3 reason in
`test_unit_coverage_complete.py`.

### Triage when deciding whether a tool needs tests

- **Tier 1 — test thoroughly.** Real logic: unit math, parsing, classification,
  path/name resolution, state tallies. (model_inspect, sys_get_selection,
  cam_get/_cam_common, _data_common/_doc_common, _param_common, design_configure,
  joint_create, joint_create_origin, _cam_templates, sketch_add_geometry.)
- **Tier 2 — test the one or two real helpers.** Mostly Fusion orchestration
  with a pure helper or two worth pinning. (doc_open URN parsing, quoting
  helpers, design_get tree/timeline slices,
  doc_update_xref/cam_generate helpers.)
- **Tier 3 — skip.** Fusion pass-throughs with no pure logic. Skipping is
  correct, not lazy.

## How the harness works (`conftest.py`)

Two problems make these tools awkward to import in a test, and `conftest.py`
solves both:

1. **Module-top `adsk` access.** Each tool does `app =
   adsk.core.Application.get()` at import time. So `install_mock_adsk()` injects
   mock `adsk` / `adsk.core` / `adsk.fusion` / `adsk.cam` into `sys.modules`
   **before** any tool is imported (it's called at collection time).
2. **Importing the package pulls in Fusion-dependent code.** `entry.py`
   auto-discovers and imports every tool (most need Fusion) and
   `commands/__init__.py` builds UI panels. `load_tool("model_inspect")`
   sidesteps both: it puts `commands/` on the path, imports only the cheap
   adsk-free packages, stubs `mcpServer.tools`, then spec-loads the single
   requested module so its `from ..mcp_primitives ...` relative imports resolve.

```python
from conftest import load_tool
mi = load_tool("model_inspect")   # at module level
```

### The one rule the mocks impose: assert on concrete values

`adsk.core` / `adsk.fusion` / `adsk.cam` are `unittest.mock.Mock` objects.
Unmodeled attribute access returns a **truthy child Mock**, not `None` and not
an error. So:

- `assert result is not None` is almost always true and proves nothing.
- `assert payload["x"] == 50.0` catches a real bug.

A few `app.*` reads are pre-seeded with real values (`app.activeDocument.name =
"TestDoc"`, `app.version`) and a few `.cast` methods are pass-throughs
(`Design.cast`, `Operation.cast`) so that tools which filter on a cast result
behave correctly. If a tool reads some `adsk` attribute that returns a stray
Mock and pollutes a JSON payload, fix it **in the harness** (model that
attribute) rather than in each test.

### Fakes: extend the shared ones

Every unit test stands on the shared fakes under `tests/fakes/`, one module per
Fusion family over a scaffold module the families share. `conftest.py`
re-exports every name, so a test imports its fakes from conftest (`from conftest
import BRepBody`) and a new fake joins its family's module. `make_design` /
`MakeComp` / `MakeDesign` build a design, and `install(mod, design)` wires it
into a tool. The smaller classes are named after Fusion's runtime type names,
because tools branch on `type(x).__name__`: `BRepFace`, `BRepEdge`, `Plane`,
`Cylinder`, `Line3D`, `Circle3D`, `BRepBody`, `FakeVector3D`, `FakePoint`. They
implement only the interface a tool reads.

When `MakeComp`/`MakeDesign` lack a surface your tool needs, extend the shared
fake; don't fork a bespoke `Fake*` hierarchy into your test file. A type whose
shape was measured in live Fusion (a key of `live_api_facts.SHAPES`) uses its
shared fake: import it, or subclass it and add only the extra the test needs.
`test_fake_shapes_exist.py` compares each shared fake's attributes with the
measured shape, and refuses a free-standing local double of a measured type,
because that comparison never reads a local copy. A type with no measured shape
keeps a local double, whose one-line docstring says so.

## Adding or updating a test

[CLAUDE.md](CLAUDE.md) is the recipe: which pattern to copy (a rich read, a fuller fake object
model, or a pure function), the shape every new test follows, and how to update a test when the
behavior it pins changes.

## Offline API change-impact report

`api_change_report.py` compares the API declarations of two Fusion builds and lists the tools and
tests a change may affect. Its declaration parser comes from the API explorer, and it shares the
exact-byte AST loader with `gen_api_surface.py`. It does not import `adsk`, contact Fusion, regenerate facts,
or change live receipts. Capture each build from an explicit `adsk` directory containing `.py`
bindings, then compare two snapshots with the same declaration representation:

```powershell
py -3 tests/api_change_report.py snapshot --bindings-dir "C:\path\to\Api\Python\packages\adsk" --build-label "2705.1.15" --out outputs/api-history/2705.1.15.json
py -3 tests/api_change_report.py diff outputs/api-history/before.json outputs/api-history/after.json --out outputs/api-history/impact.json
```

The build label is whatever you pass; nothing checks it against the installed build. Snapshots
record exact binding paths, byte SHA-256 hashes, scanner hashes, available modules, and absent known
namespaces. A webdeploy channel/directory ID is recorded when present in the path. Existing
snapshots and reports are never overwritten, so choose a new filename for another capture.
Snapshots carry a content digest checked before comparison. Keep the original snapshots rather than
editing their labels or declarations, and recapture a snapshot saved in an older exploratory format.

The diff refuses incompatible formats, namespace scopes, or SWIG-versus-Python representations.
It compares only namespaces available on both sides; a newly available or unavailable namespace
is reported separately, never as a batch of symbol additions/removals. Changed records include
method overload signatures, property readability/writability and setter signatures, enum/constant
expressions or literal values, documentation hashes, and preview/retired/unsupported wording markers.
SWIG references to native enum constants do not reveal their numeric values. Generic `*args`
signatures and documentation markers are declarations, not verified runtime contracts.

`--repo PATH` selects the source checkout to map against (default: this command's checkout).
Affected tools and acceptance cases are explicitly `syntactic_candidate`: attribute names and
local import chains identify leads; unit filenames, literal live rows, and explicit tool mentions
identify candidate checks. Source hashes and line locations accompany them. A match is a lead, not
proof: text matching can hit common names and miss dynamic references or scenarios that never name a
tool, and the report neither runs the candidate tests nor certifies them sufficient. An empty match
does not prove no impact, and a zero-change report proves only that the compared declaration records
match.

Focused verification: `py -3 -m pytest tests/unit/test_api_change_report.py tests/unit/test_generators.py -q`.
