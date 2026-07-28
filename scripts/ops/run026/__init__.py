"""Run026 ops-park scripts: which declared tables a real database actually has.

Read-only, like every script under ``scripts/ops/``. Safety primitives are
reused from ``scripts.ops.run021._common`` rather than copied, so there is one
implementation of the ``--apply`` / ``--i-understand-prod`` contract.
"""
