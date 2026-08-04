"""TEMPORARY probe. Deliberately violates formatting so exactly one CI job fails.

Purpose: confirm that `All Checks Passed` reports FAILURE rather than SKIPPED when an
upstream job fails, before it is added as a required status check. A skipped required
check is reported by GitHub as successful, so this must be observed and not assumed.

This branch is never merged.
"""
x=[1,  2,3]
def  badly_formatted( a,b ):
        return a+b
