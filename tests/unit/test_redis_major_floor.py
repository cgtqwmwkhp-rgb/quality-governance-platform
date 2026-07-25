"""Guard: redis-py major floor and call-site async API surface."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_requirements_floor_is_redis_8x() -> None:
    req = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "redis>=8.0.1,<9.0.0" in req
    assert "redis>=5.0.0,<8.0.0" not in req


def test_lockfile_pins_redis_8x() -> None:
    lock = (REPO_ROOT / "requirements.lock").read_text(encoding="utf-8")
    lines = [line for line in lock.splitlines() if line.startswith("redis==")]
    assert lines, "redis pin missing from lock"
    version = lines[0].split("==", 1)[1].split("\\", 1)[0].strip()
    major = int(version.split(".", 1)[0])
    assert major == 8, f"expected redis 8.x lock pin, got {version}"


def test_runtime_call_sites_use_redis_asyncio() -> None:
    paths = [
        "src/infrastructure/cache/redis_cache.py",
        "src/infrastructure/middleware/rate_limiter.py",
        "src/api/middleware/idempotency.py",
        "src/api/routes/health.py",
    ]
    for rel in paths:
        body = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "redis.asyncio" in body or "import redis.asyncio" in body, rel
