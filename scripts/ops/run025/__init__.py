"""Run025 ops-park scripts: tenant attribution and model/schema parity.

Read-only by default, like every script under ``scripts/ops/``. Safety
primitives are reused from ``scripts.ops.run021._common`` rather than copied, so
there is one implementation of the ``--apply`` / ``--i-understand-prod``
contract.
"""
