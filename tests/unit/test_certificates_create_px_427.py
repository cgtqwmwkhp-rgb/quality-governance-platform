"""POST /compliance-automation/certificates — the register's first writer (PX-427).

The register shipped with three read routes and no writer, so ``POST`` answered
405 and the only way a dated certificate could reach ``certificates`` was a
hand-written SQL insert. ``CertificateCreate`` existed but named ``issued_by`` /
``issued_date``, which match no column and no caller, so wiring it up as written
would have dropped the issuer and the issue date on every write.

Three things are held here, because each is a way the fix could look done and not
be:

* the request schema names real columns, and still rejects unknown fields;
* the writer stamps ``tenant_id`` and stores naive **UTC**, so asyncpg accepts
  the bind and the recorded instant is the one the caller sent;
* a dated ISO 9001 certificate actually reaches the matrix framework countdown,
  which is the observable the operator was blocked on (LIVE-05).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from src.api.schemas.compliance_automation import CertificateCreate
from src.domain.models.compliance_automation import Certificate
from src.domain.services.assurance_cert_shelf_service import AssuranceCertShelfService
from src.domain.services.compliance_automation_service import ComplianceAutomationService
from src.domain.services.standards_cell_aggregate_service import roll_framework_countdown

ISSUE = datetime(2026, 8, 1, tzinfo=timezone.utc)
EXPIRY = datetime(2027, 8, 1, tzinfo=timezone.utc)


def _db(assigned_id: int = 11):
    """An AsyncSession stand-in that assigns an id on flush, as Postgres would."""
    db = SimpleNamespace(add=MagicMock(), flush=AsyncMock(), refresh=AsyncMock())

    async def assign_id():
        for call in db.add.call_args_list:
            obj = call.args[0]
            if isinstance(obj, Certificate) and getattr(obj, "id", None) is None:
                obj.id = assigned_id

    db.flush.side_effect = assign_id
    return db


def _service(db) -> ComplianceAutomationService:
    return ComplianceAutomationService(db=db)  # type: ignore[arg-type]


async def _create(db, **overrides):
    payload = {
        "tenant_id": 3,
        "name": "ISO 9001:2015 Certificate",
        "certificate_type": "iso9001",
        "entity_type": "organisation",
        "issue_date": ISSUE,
        "expiry_date": EXPIRY,
    }
    payload.update(overrides)
    return await _service(db).create_certificate(**payload)


class TestRequestSchemaNamesRealColumns:
    """The dead-schema failure, turned into a guard.

    Comparing against ``Certificate.__table__`` rather than a hand-copied list is
    the point: a column rename breaks this test instead of quietly reintroducing
    a field that writes nowhere.
    """

    def test_every_request_field_is_a_certificate_column(self) -> None:
        columns = set(Certificate.__table__.columns.keys())
        unknown = sorted(set(CertificateCreate.model_fields) - columns)
        assert not unknown, (
            f"CertificateCreate declares {unknown}, which are not columns on `certificates`. "
            "A field that names no column is silently discarded on write — the PX-427 defect."
        )

    def test_the_dead_field_names_are_rejected(self) -> None:
        """``issued_by`` / ``issued_date`` must not be quietly accepted again."""
        with pytest.raises(ValidationError):
            CertificateCreate(
                name="ISO 9001",
                certificate_type="iso9001",
                entity_type="organisation",
                issued_by="BSI",  # type: ignore[call-arg]
                issued_date=ISSUE,  # type: ignore[call-arg]
                issue_date=ISSUE,
                expiry_date=EXPIRY,
            )

    def test_unknown_body_fields_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CertificateCreate(
                name="ISO 9001",
                certificate_type="iso9001",
                entity_type="organisation",
                issue_date=ISSUE,
                expiry_date=EXPIRY,
                totally_made_up="x",  # type: ignore[call-arg]
            )

    def test_dates_are_required(self) -> None:
        """An undated certificate is exactly what the countdown cannot report."""
        with pytest.raises(ValidationError):
            CertificateCreate(
                name="ISO 9001",
                certificate_type="iso9001",
                entity_type="organisation",
            )

    def test_expiry_before_issue_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CertificateCreate(
                name="ISO 9001",
                certificate_type="iso9001",
                entity_type="organisation",
                issue_date=EXPIRY,
                expiry_date=ISSUE,
            )

    def test_mixed_offset_and_offset_free_dates_compare_without_error(self) -> None:
        """A date-only issue plus a zulu expiry must validate, not 500.

        Pydantic parses each field on its own, so ``2026-08-01`` arrives naive
        while ``2027-08-01T00:00:00Z`` arrives aware. Comparing those two
        directly raises ``TypeError`` from inside the validator.
        """
        model = CertificateCreate(
            name="ISO 9001",
            certificate_type="iso9001",
            entity_type="organisation",
            issue_date="2026-08-01",  # type: ignore[arg-type]
            expiry_date="2027-08-01T00:00:00Z",  # type: ignore[arg-type]
        )
        assert model.issue_date.tzinfo is None
        assert model.expiry_date.tzinfo is not None


class TestWriter:
    @pytest.mark.asyncio
    async def test_stamps_tenant_and_returns_the_stored_row(self) -> None:
        db = _db()
        row = await _create(db, issuing_body="BSI", entity_name="Plantexpand Ltd", reference_number="FS 123456")

        db.add.assert_called_once()
        stored = db.add.call_args.args[0]
        assert isinstance(stored, Certificate)
        # A NULL tenant_id reads back as visible to every tenant, so this is the
        # isolation assertion, not a bookkeeping one.
        assert stored.tenant_id == 3
        assert row["id"] == 11
        assert row["name"] == "ISO 9001:2015 Certificate"
        assert row["issuing_body"] == "BSI"
        assert row["entity_name"] == "Plantexpand Ltd"
        assert row["reference_number"] == "FS 123456"

    @pytest.mark.asyncio
    async def test_post_row_matches_the_list_read_shape(self) -> None:
        """What POST reports back is what the following GET shows."""
        db = _db()
        created = await _create(db)
        stored = db.add.call_args.args[0]

        list_db = SimpleNamespace(
            execute=AsyncMock(
                return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[stored]))))
            )
        )
        listed = await _service(list_db).get_certificates(tenant_id=3)
        assert listed == [created]

    @pytest.mark.asyncio
    async def test_aware_dates_are_stored_as_naive_utc(self) -> None:
        db = _db()
        await _create(db)
        stored = db.add.call_args.args[0]

        assert stored.issue_date.tzinfo is None
        assert stored.expiry_date.tzinfo is None
        assert stored.expiry_date == datetime(2027, 8, 1)

    @pytest.mark.asyncio
    async def test_offsets_are_converted_not_discarded(self) -> None:
        """``+01:00`` must move the instant, not have its offset dropped.

        Dropping it stores 00:00 local as 00:00 UTC, and every reader of this
        column re-attaches UTC — so the recorded expiry would sit an hour late
        and cross a day boundary.
        """
        db = _db()
        await _create(db, expiry_date=datetime(2027, 8, 1, 0, 30, tzinfo=timezone(timedelta(hours=1))))
        stored = db.add.call_args.args[0]

        assert stored.expiry_date == datetime(2027, 7, 31, 23, 30)

    @pytest.mark.asyncio
    async def test_naive_dates_pass_through_unchanged(self) -> None:
        db = _db()
        await _create(db, issue_date=datetime(2026, 8, 1), expiry_date=datetime(2027, 8, 1))
        stored = db.add.call_args.args[0]

        assert stored.expiry_date == datetime(2027, 8, 1)

    @pytest.mark.asyncio
    async def test_entity_id_defaults_to_the_tenant_for_an_org_level_cert(self) -> None:
        """The column is NOT NULL and a company accreditation names no row inside the tenant."""
        db = _db()
        row = await _create(db)
        assert row["entity_id"] == "3"

    @pytest.mark.asyncio
    async def test_supplied_entity_id_is_kept(self) -> None:
        db = _db()
        row = await _create(db, entity_type="equipment", entity_id="asset-9001")
        assert row["entity_id"] == "asset-9001"

    @pytest.mark.asyncio
    async def test_writer_does_not_stamp_a_status(self) -> None:
        """Nothing recomputes ``status``, so the writer must not stamp a verdict.

        Readers grade from ``expiry_date`` on every read; a stored verdict would
        be a snapshot that goes stale with no way to tell. ``status`` is left
        unset here so the column default supplies it — this asserts the writer
        assigned nothing, not that the persisted value is null.
        """
        db = _db()
        await _create(db, expiry_date=datetime(2020, 1, 1, tzinfo=timezone.utc), issue_date=datetime(2019, 1, 1))
        stored = db.add.call_args.args[0]
        assert stored.status is None


class TestFrameworkCountdownLeavesNoDatedCert:
    """LIVE-05: the observable the operator was actually blocked on.

    Exercised from a real ``Certificate`` through the shelf that composes the
    matrix countdown, rather than from a hand-built shelf dict — the attribution
    step in the middle is the part that decides whether a register row counts.
    """

    @staticmethod
    def _shelf_db(certificate: Certificate):
        def rows(values):
            return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=values))))

        # get_shelf reads register, Planet Mark, UVDB, then Library, in that order.
        return SimpleNamespace(execute=AsyncMock(side_effect=[rows([certificate]), rows([]), rows([]), rows([])]))

    @pytest.mark.asyncio
    async def test_dated_9001_cert_sets_the_9001_countdown(self) -> None:
        db = _db()
        await _create(db)
        stored = db.add.call_args.args[0]

        shelf = await AssuranceCertShelfService(self._shelf_db(stored)).get_shelf(tenant_id=3)  # type: ignore[arg-type]
        countdown = roll_framework_countdown(
            shelf["items"],
            frameworks=["9001", "14001"],
            today=EXPIRY.date() - timedelta(days=19),
        )

        nine_thousand_one = countdown["frameworks"]["9001"]
        assert nine_thousand_one["status"] == "due_soon"
        assert nine_thousand_one["days_remaining"] == 19
        assert nine_thousand_one["next_expiry"] == "2027-08-01"
        # A 9001 certificate must not paint a column it does not prove.
        assert countdown["frameworks"]["14001"]["status"] == "none"

    @pytest.mark.asyncio
    async def test_a_pat_test_still_paints_no_framework(self) -> None:
        """Attribution stays honest: the writer must not make the register prove everything."""
        db = _db()
        await _create(db, name="PAT testing 2026", certificate_type="equipment")
        stored = db.add.call_args.args[0]

        shelf = await AssuranceCertShelfService(self._shelf_db(stored)).get_shelf(tenant_id=3)  # type: ignore[arg-type]
        countdown = roll_framework_countdown(shelf["items"], frameworks=["9001"], today=ISSUE.date())

        assert countdown["frameworks"]["9001"]["status"] == "none"
        assert countdown["unmatched_on_shelf"] is True
