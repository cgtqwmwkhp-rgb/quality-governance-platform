"""Integration tests for audit version control and entity decoding integrity."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.routes.audits import (
    create_run,
    create_template,
    get_template,
    publish_template,
    update_template,
)
from src.api.schemas.audit import (
    AuditRunCreate,
    AuditTemplateCreate,
    AuditTemplateUpdate,
)
from src.domain.models.audit import AuditQuestion, AuditRun, AuditSection, AuditTemplate
from src.domain.models.user import User


@pytest.fixture
async def isolated_db_session():
    """Create an isolated async SQLite session with only required tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(User.__table__.create)
        await conn.run_sync(AuditTemplate.__table__.create)
        await conn.run_sync(AuditSection.__table__.create)
        await conn.run_sync(AuditQuestion.__table__.create)
        await conn.run_sync(AuditRun.__table__.create)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_user(isolated_db_session: AsyncSession):
    user = User(
        email="audit.integrity@test.local",
        hashed_password="not-used-in-test",
        first_name="Audit",
        last_name="Tester",
        is_active=True,
        is_superuser=True,
    )
    isolated_db_session.add(user)
    await isolated_db_session.commit()
    await isolated_db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_published_template_update_increments_version_and_unpublishes(
    isolated_db_session: AsyncSession,
    test_user: User,
):
    template = await create_template(
        template_data=AuditTemplateCreate(
            name="Safety &amp; Compliance Template",
            description="Initial",
            category="Safety",
        ),
        db=isolated_db_session,
        current_user=test_user,
    )
    # Required before publish
    section = AuditSection(template_id=template.id, title="General", sort_order=0, weight=1.0)
    isolated_db_session.add(section)
    await isolated_db_session.flush()
    isolated_db_session.add(
        AuditQuestion(
            template_id=template.id,
            section_id=section.id,
            question_text="Are checks completed?",
            question_type="yes_no",
            sort_order=0,
            weight=1.0,
        )
    )
    await isolated_db_session.commit()
    published = await publish_template(template.id, db=isolated_db_session, current_user=test_user)
    assert published.is_published is True
    assert published.version == 1

    updated = await update_template(
        template_id=template.id,
        template_data=AuditTemplateUpdate(description="Updated description"),
        db=isolated_db_session,
        current_user=test_user,
    )

    assert updated.version == 2
    assert updated.is_published is False


@pytest.mark.asyncio
async def test_run_captures_template_version_snapshot(
    isolated_db_session: AsyncSession,
    test_user: User,
):
    template = await create_template(
        template_data=AuditTemplateCreate(
            name="Operational Template",
            description="Template used for version snapshot",
            category="Operational",
        ),
        db=isolated_db_session,
        current_user=test_user,
    )

    # Add one section/question so template can be published.
    section = AuditSection(template_id=template.id, title="Section A", description="Checks", sort_order=0, weight=1.0)
    isolated_db_session.add(section)
    await isolated_db_session.flush()
    isolated_db_session.add(
        AuditQuestion(
            template_id=template.id,
            section_id=section.id,
            question_text="Is equipment safe?",
            question_type="yes_no",
            sort_order=0,
            weight=1.0,
        )
    )
    await isolated_db_session.commit()

    published = await publish_template(template.id, db=isolated_db_session, current_user=test_user)
    assert published.version == 1

    run = await create_run(
        run_data=AuditRunCreate(template_id=template.id, title="Versioned run"),
        db=isolated_db_session,
        current_user=test_user,
    )

    assert run.template_version == 1


@pytest.mark.asyncio
async def test_template_detail_decodes_html_entities_for_questions_and_options(
    isolated_db_session: AsyncSession,
    test_user: User,
):
    template = await create_template(
        template_data=AuditTemplateCreate(
            name="Welfare &amp; Safety",
            description="Checks &amp; controls",
            category="Health &amp; Safety",
        ),
        db=isolated_db_session,
        current_user=test_user,
    )
    section = AuditSection(
        template_id=template.id,
        title="Area &amp; Access",
        description="Exit &amp; route checks",
        sort_order=0,
        weight=1.0,
    )
    isolated_db_session.add(section)
    await isolated_db_session.flush()
    isolated_db_session.add(
        AuditQuestion(
            template_id=template.id,
            section_id=section.id,
            question_text="Are welfare areas clean &amp; tidy?",
            question_type="dropdown",
            options_json=[
                {"value": "yes", "label": "Yes &amp; compliant"},
                {"value": "no", "label": "No &amp; non-compliant"},
            ],
            sort_order=0,
            weight=1.0,
        )
    )
    await isolated_db_session.commit()

    detail = await get_template(template.id, db=isolated_db_session, current_user=test_user)

    assert detail.name == "Welfare & Safety"
    assert detail.category == "Health & Safety"
    assert detail.sections[0].title == "Area & Access"
    assert detail.sections[0].questions[0].question_text == "Are welfare areas clean & tidy?"
    assert detail.sections[0].questions[0].options[0].label == "Yes & compliant"
