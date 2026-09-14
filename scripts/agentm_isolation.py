#!/usr/bin/env python3
"""agentm_isolation.py -- let a real-bridge test class's agentm modules import
their own siblings for as long as the class runs.

agentm's memory scripts import their siblings by bare name (`import
vault_layout`), at module level and inside functions. A bare import returns
whatever sys.modules already holds under that name, else the first match on
sys.path. The unit suite is one process, and discovery imports every test file
before any test runs, so a crickets module under the same name is often
already there: the wiki plugin's vault_layout.py, whose API differs.

The research bridge's _load_module kept that module away only while agentm's
module executed (#249), so an import agentm made later, inside a function, ran
against whatever the process held by then. recall.py imports lifecycle that
way, and lifecycle's own `import vault_layout` was handed the wiki's module in
four suites, which passed only because none of them asserts on lifecycle's
sidecar. isolate_agentm_imports() sets such modules aside for the life of the
class instead, with agentm's scripts dir first on sys.path, and a class cleanup
puts them back. The bridges have since run every load and call inside their own
_agentm_names; this still covers whatever else a class does with agentm.

Not named test_*.py, so discovery never collects it. stdlib only.
"""
from __future__ import annotations

import sys
from pathlib import Path


def isolate_agentm_imports(test_class, scripts_dir) -> None:
    """Until `test_class` has torn down, make agentm's bare sibling imports
    resolve to `scripts_dir`. Every loaded module that holds the name of a
    script there but came from another file is set aside, and `scripts_dir`
    goes first on sys.path. A class cleanup undoes both, and class cleanups run
    after tearDownClass, so the modules come back after the class's own purge.

    Call it in setUpClass before the first agentm load. With `scripts_dir` None
    (no agentm checkout, so the class is about to skip) it does nothing.
    """
    if scripts_dir is None:
        return
    scripts_dir = Path(scripts_dir).resolve()
    set_aside = {}
    for name in sys.modules.keys() & {p.stem for p in scripts_dir.glob("*.py")}:
        f = getattr(sys.modules[name], "__file__", None)
        if f and Path(f).resolve().parent != scripts_dir:
            set_aside[name] = sys.modules.pop(name)
    entry = str(scripts_dir)
    sys.path.insert(0, entry)

    def restore():
        if entry in sys.path:
            sys.path.remove(entry)
        sys.modules.update(set_aside)

    test_class.addClassCleanup(restore)
