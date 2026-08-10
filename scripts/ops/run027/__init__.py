"""Run027 ops park — duplicate register remediation.

Two scripts, deliberately asymmetric in what they are allowed to do:

``purge_duplicate_audit_runs``
    Hard-deletes named ``audit_runs`` rows and everything that belongs to them.
    It only ever acts on reference numbers passed explicitly on the command line,
    because a delete of a governed record is authorised by a human naming the
    record, never by a heuristic recognising it.

``inventory_duplicate_registers``
    Finds *candidate* duplicates across the audit, risk, action and case
    registers. Report-only, with no ``--apply`` to forget to leave off. What it
    finds is an input to a human review, not a work queue.
"""
