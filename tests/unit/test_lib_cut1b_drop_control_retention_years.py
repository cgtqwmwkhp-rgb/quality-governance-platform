"""CUT-1b — the control layer stops being a second retention system of record.

``controlled_documents.retention_period_years`` was declared
``mapped_column(Integer, default=7)``. A SQLAlchemy ``default`` is a writer: every
controlled document ever created carried seven years, which is Citation (ATLAS)'s
flat "7 Years / all employees" position expressed as code — on documents whose
category says three years, or forty. Its single reader turned that seven into the
obsolete archive's ``retention_end_date``.

Three properties are load-bearing here, and each has a section below.

1. **The column is gone, and nothing writes or reads it.** Not just dropped from
   the table: absent from the mapper, absent from application source, and absent
   from every alembic revision except the one that created it and the one that
   drops it.
2. **Nothing invented a shorter clock to replace it.** The obsolete archive's end
   date now comes from the Register row — the one retention SoR (F-7 §2) — and is
   ``NULL`` whenever the Register cannot answer. Disposal hard-deletes, so an
   unanswerable question must produce "keep", never a plausible-looking date.
3. **Seven is not reachable by any path.** A forty-year record gets forty.
"""

from __future__ import annotations

import ast
import io
import tokenize
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.routes.document_control import _archive_retention_end_date
from src.domain.models.document import Document
from src.domain.models.document_control import ControlledDocument
from src.domain.services.document_library_filing_service import apply_supersede_retention, supersede_retention_until

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = REPO_ROOT / "alembic" / "versions"
MIGRATION = VERSIONS_DIR / "20261104_lib_cut1b_drop_control_retention_years.py"
CREATE_MIGRATION = VERSIONS_DIR / "20260711_create_controlled_documents.py"

CUT1B_REVISION = "20261104_lib_cut1b_drop"
STEWARD14_REVISION = "20261103_lib_steward14"

COLUMN = "retention_period_years"

#: Citation (ATLAS)'s flat position, and the value the dropped column defaulted
#: to. Named so the assertions that forbid it read as the governance statement
#: they are, rather than as a magic number.
CITATION_FLAT_YEARS = 7

TENANT = 1
OTHER_TENANT = 2

#: A leap day, so the calendar-year arithmetic is actually exercised rather than
#: coincidentally agreeing with a 365-day approximation.
OBSOLETED_AT = datetime(2028, 2, 29, 9, 30)


# ---------------------------------------------------------------------------
# 1. The column is gone, and nothing writes or reads it
# ---------------------------------------------------------------------------


def test_the_control_record_no_longer_maps_a_retention_period() -> None:
    assert COLUMN not in {column.name for column in ControlledDocument.__table__.columns}
    assert not hasattr(ControlledDocument, COLUMN)


def test_the_control_record_holds_no_retention_field_under_any_name() -> None:
    """A rename is the same defect wearing a different label.

    ``disposal_method`` is how a document is destroyed, not when, so it is not a
    second clock and stays.
    """
    retention_columns = [column.name for column in ControlledDocument.__table__.columns if "retention" in column.name]
    assert retention_columns == [], (
        "the control record must hold no retention fact of its own — the Register row is the SoR "
        f"(F-7 §2); found {retention_columns}"
    )


def _source_without_comments_or_docstring(path: Path) -> str:
    """The executable text of a module: comments and module docstring removed.

    A docstring or comment naming the column is documentation — the drop
    migration and the model both explain what went and why. A *code* reference is
    a writer or a reader, and that is what this slice had to end.
    """
    text = path.read_text(encoding="utf-8")
    without_comments = "".join(
        token.string if token.type != tokenize.COMMENT else ""
        for token in tokenize.generate_tokens(io.StringIO(text).readline)
    )
    module_docstring = ast.get_docstring(ast.parse(text))
    if module_docstring:
        without_comments = without_comments.replace(module_docstring, "")
    return without_comments


def _python_sources(*relative_dirs: str) -> list[Path]:
    files: list[Path] = []
    for relative in relative_dirs:
        files.extend(
            path for path in (REPO_ROOT / relative).rglob("*.py") if path.is_file() and "__pycache__" not in path.parts
        )
    return sorted(files)


def test_no_application_code_writes_or_reads_the_dropped_column() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _python_sources("src", "scripts")
        if COLUMN in _source_without_comments_or_docstring(path)
    ]
    assert offenders == [], (
        f"{COLUMN} was dropped; these still reference it in code and will fail against a "
        f"migrated database: {offenders}"
    )


def test_no_frontend_code_references_the_dropped_column() -> None:
    frontend = REPO_ROOT / "frontend" / "src"
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in frontend.rglob("*")
        if path.is_file()
        and path.suffix in {".ts", ".tsx", ".js", ".jsx"}
        and COLUMN in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == [], f"the frontend must not read a column that no longer exists: {offenders}"


def test_only_the_create_and_the_drop_revisions_name_the_column_in_code() -> None:
    """CUT-1 and STEWARD-14 name it in their docstrings — as the work they deferred.

    That is history and stays readable. Code that touches the column may only
    exist in the revision that created it and the revision that removes it.
    """
    naming_it = {
        path.name
        for path in VERSIONS_DIR.rglob("*.py")
        if path.is_file() and COLUMN in _source_without_comments_or_docstring(path)
    }
    assert naming_it == {CREATE_MIGRATION.name, MIGRATION.name}, naming_it


# ---------------------------------------------------------------------------
# 2. The obsolete archive's end date comes from the Register, or is NULL
# ---------------------------------------------------------------------------


@pytest.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Document.__table__.create)
    async with session_factory() as db:
        yield db
    await engine.dispose()


async def _register_row(
    db: AsyncSession,
    *,
    tenant_id: int = TENANT,
    retention_years: Optional[int] = None,
    retention_anchor: Optional[str] = None,
    retention_until: Optional[datetime] = None,
) -> int:
    document = Document(
        tenant_id=tenant_id,
        title="Register row under control",
        file_name="register-row.pdf",
        file_type="pdf",
        file_size=1024,
        file_path="/blob/register-row.pdf",
        reference_number=f"REG-{tenant_id}-{retention_anchor or 'none'}",
        retention_years=retention_years,
        retention_anchor=retention_anchor,
        retention_basis="Current + superseded 6 years" if retention_anchor else None,
        retention_until=retention_until,
    )
    db.add(document)
    await db.flush()
    return document.id


async def _end_date(db: AsyncSession, library_document_id: Optional[int]) -> Optional[datetime]:
    return await _archive_retention_end_date(
        db,
        tenant_id=TENANT,
        library_document_id=library_document_id,
        obsoleted_at=OBSOLETED_AT,
    )


async def test_an_unanchored_control_record_gets_no_end_date(session) -> None:
    """No Register row means no retention SoR to ask, so the archive is kept."""
    assert await _end_date(session, None) is None


async def test_a_supersede_anchored_register_row_starts_its_clock_at_obsolescence(session) -> None:
    document_id = await _register_row(session, retention_years=6, retention_anchor="supersede")
    assert await _end_date(session, document_id) == datetime(2034, 2, 28, 9, 30)


async def test_the_years_are_calendar_years_not_365_day_years(session) -> None:
    """``* 365`` lands ten days early on forty years, and disposal hard-deletes."""
    document_id = await _register_row(session, retention_years=40, retention_anchor="supersede")
    end_date = await _end_date(session, document_id)
    assert end_date == datetime(2068, 2, 29, 9, 30)
    assert end_date is not None and end_date > OBSOLETED_AT + timedelta(days=40 * 365)


async def test_a_forty_year_record_gets_forty_years_not_citations_seven(session) -> None:
    """The defect this slice closes, stated as an assertion."""
    document_id = await _register_row(session, retention_years=40, retention_anchor="supersede")
    end_date = await _end_date(session, document_id)
    assert end_date is not None
    assert end_date.year - OBSOLETED_AT.year == 40 != CITATION_FLAT_YEARS


async def test_an_issue_anchored_row_keeps_the_date_it_was_filed_with(session) -> None:
    """Its clock started at approval; being obsoleted does not restart it."""
    filed_until = datetime(2030, 5, 1, tzinfo=timezone.utc)
    document_id = await _register_row(
        session,
        retention_years=3,
        retention_anchor="issue",
        retention_until=filed_until,
    )
    assert await _end_date(session, document_id) == datetime(2030, 5, 1)


async def test_a_legacy_register_row_with_no_policy_gets_no_end_date(session) -> None:
    """Pre-CUT-1 rows carry no policy. CUT-1c is deferred, so the answer is keep."""
    document_id = await _register_row(session)
    assert await _end_date(session, document_id) is None


async def test_an_event_anchored_row_gets_no_end_date(session) -> None:
    """ "Life of asset + 6 years" — QGP does not hold the event, so it cannot compute."""
    document_id = await _register_row(session, retention_years=6, retention_anchor="event")
    assert await _end_date(session, document_id) is None


async def test_an_indefinite_row_gets_no_end_date(session) -> None:
    document_id = await _register_row(session, retention_anchor="indefinite")
    assert await _end_date(session, document_id) is None


async def test_a_register_row_belonging_to_another_tenant_is_not_read(session) -> None:
    """Cross-tenant read would be a leak; refusing it must also fail safe."""
    document_id = await _register_row(session, tenant_id=OTHER_TENANT, retention_years=6, retention_anchor="supersede")
    assert await _end_date(session, document_id) is None


async def test_a_dangling_anchor_gets_no_end_date(session) -> None:
    """``library_document_id`` is ``ON DELETE SET NULL``, but a stale id must not raise."""
    assert await _end_date(session, 9999) is None


async def test_the_end_date_is_naive_for_the_column_it_is_written_to(session) -> None:
    """``obsolete_document_records.retention_end_date`` is ``timestamp without time zone``.

    asyncpg refuses to adapt an aware datetime for such a column and raises, which
    surfaces as a 500 and is not reproduced by SQLite.
    """
    document_id = await _register_row(session, retention_years=6, retention_anchor="supersede")
    end_date = await _end_date(session, document_id)
    assert end_date is not None and end_date.tzinfo is None


# ---------------------------------------------------------------------------
# The shared helper the Register's own supersede path uses
# ---------------------------------------------------------------------------


def _register_document(**kwargs) -> Document:
    return Document(title="t", **kwargs)


def test_the_supersede_helper_never_brings_a_disposal_date_forward() -> None:
    """A legacy row's issue-anchored date is too early for a supersede rule."""
    document = _register_document(
        retention_years=6,
        retention_anchor="supersede",
        retention_basis="Current + superseded 6 years",
        retention_until=datetime(2029, 1, 1, tzinfo=timezone.utc),
    )
    resolved = supersede_retention_until(document, datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert resolved == datetime(2036, 1, 1, tzinfo=timezone.utc)


def test_the_supersede_helper_keeps_a_later_stored_date() -> None:
    document = _register_document(
        retention_years=2,
        retention_anchor="supersede",
        retention_basis="Current + previous 2 years",
        retention_until=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    resolved = supersede_retention_until(document, datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert resolved == datetime(2099, 1, 1, tzinfo=timezone.utc)


def test_reading_the_supersede_date_does_not_write_it() -> None:
    """The control layer asks the Register; it must not become a second writer."""
    document = _register_document(
        retention_years=6,
        retention_anchor="supersede",
        retention_basis="Current + superseded 6 years",
        retention_until=None,
    )
    supersede_retention_until(document, datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert document.retention_until is None


def test_apply_supersede_retention_still_writes_through_the_shared_helper() -> None:
    """The Register's own supersede path is unchanged by the extraction."""
    document = _register_document(
        retention_years=6,
        retention_anchor="supersede",
        retention_basis="Current + superseded 6 years",
        retention_until=datetime(2029, 1, 1, tzinfo=timezone.utc),
    )
    apply_supersede_retention(document, datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert document.retention_until == datetime(2036, 1, 1, tzinfo=timezone.utc)


def test_apply_supersede_retention_leaves_a_non_supersede_row_alone() -> None:
    already = datetime(2029, 1, 1, tzinfo=timezone.utc)
    document = _register_document(
        retention_years=3,
        retention_anchor="issue",
        retention_basis="3 years",
        retention_until=already,
    )
    apply_supersede_retention(document, datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert document.retention_until is already


# ---------------------------------------------------------------------------
# 3. The migration
# ---------------------------------------------------------------------------


def _migration_constant(name: str) -> object:
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            assert node.value is not None
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {MIGRATION.name}")


def test_migration_declares_cut1b_once_and_sits_on_steward14() -> None:
    assert _migration_constant("revision") == CUT1B_REVISION
    assert _migration_constant("down_revision") == STEWARD14_REVISION
    declarers = [
        path
        for path in VERSIONS_DIR.rglob("*.py")
        if path.is_file() and f'revision: str = "{CUT1B_REVISION}"' in path.read_text(encoding="utf-8")
    ]
    assert declarers == [MIGRATION], f"exactly one file may declare {CUT1B_REVISION}, found {declarers}"


def test_migration_drops_exactly_that_column_from_exactly_that_table() -> None:
    assert _migration_constant("TABLE_NAME") == "controlled_documents"
    assert _migration_constant("COLUMN_NAME") == COLUMN

    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    drops = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"drop_column", "drop_table", "drop_index", "drop_constraint"}
    ]
    assert len(drops) == 1, "CUT-1b removes one column and nothing else"
    assert drops[0].func.attr == "drop_column"


def test_migration_writes_no_data_in_either_direction() -> None:
    """A retention value nobody chose must not be laundered into the Register."""
    statements = [
        node.value
        for node in ast.walk(ast.parse(MIGRATION.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    for statement in statements:
        upper = statement.upper()
        for verb in ("UPDATE ", "INSERT INTO", "DELETE FROM"):
            assert verb not in upper, statement
    assert not any("documents" in s and "SELECT" in s.upper() and "controlled_documents" not in s for s in statements)


def test_migration_tolerates_an_absent_table_or_column() -> None:
    """The WI-2 / WJ-0 / CUT-1 / STEWARD-14 idempotency pattern."""
    source = MIGRATION.read_text(encoding="utf-8")
    assert "_table_exists" in source and "_columns" in source
    upgrade = source[source.index("def upgrade()") : source.index("def downgrade()")]
    assert "not in _columns(TABLE_NAME)" in upgrade
    assert "return" in upgrade


def test_downgrade_restores_the_schema_and_says_it_is_not_the_data() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    downgrade = source[source.index("def downgrade()") :]
    assert "add_column" in downgrade
    assert "nullable=False" in downgrade
    assert "server_default=CITATION_FLAT_YEARS" in downgrade
    assert _migration_constant("CITATION_FLAT_YEARS") == str(CITATION_FLAT_YEARS)
    assert "do not come back" in downgrade, "the downgrade must not imply the values are recoverable"
