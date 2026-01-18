"""Convert native PostgreSQL enums to VARCHAR strings.

This migration converts all enum columns from native PostgreSQL enum types
to VARCHAR strings for better portability and simpler handling.

Revision ID: convert_enums_varchar
Revises: 
Create Date: 2026-01-18

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'convert_enums_varchar'
down_revision = '02064fd78d6c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert enum columns to VARCHAR strings."""
    
    # List of all enum columns to convert: (table, column, max_length)
    enum_columns = [
        # incidents
        ('incidents', 'incident_type', 50),
        ('incidents', 'severity', 50),
        ('incidents', 'status', 50),
        # incident_actions
        ('incident_actions', 'status', 50),
        # road_traffic_collisions
        ('road_traffic_collisions', 'severity', 50),
        ('road_traffic_collisions', 'status', 50),
        # rta_actions
        ('rta_actions', 'status', 50),
        # complaints
        ('complaints', 'complaint_type', 50),
        ('complaints', 'priority', 50),
        ('complaints', 'status', 50),
        # complaint_actions
        ('complaint_actions', 'status', 50),
        # audit_runs
        ('audit_runs', 'status', 50),
        # audit_findings
        ('audit_findings', 'status', 50),
        # policies
        ('policies', 'document_type', 50),
        ('policies', 'status', 50),
        # policy_versions
        ('policy_versions', 'status', 50),
        # risks
        ('risks', 'status', 50),
        # investigation_runs
        ('investigation_runs', 'assigned_entity_type', 50),
        ('investigation_runs', 'status', 50),
    ]
    
    # For PostgreSQL, we need to convert using USING clause
    for table, column, length in enum_columns:
        # Check if table exists before attempting migration
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns 
                           WHERE table_name = '{table}' AND column_name = '{column}') THEN
                    ALTER TABLE {table} 
                    ALTER COLUMN {column} TYPE VARCHAR({length}) 
                    USING {column}::text;
                END IF;
            END $$;
        """)
    
    # Drop old enum types (they're no longer needed)
    old_enum_types = [
        'incidenttype',
        'incidentseverity', 
        'incidentstatus',
        'actionstatus',
        'rtaseverity',
        'rtastatus',
        'complainttype',
        'complaintpriority',
        'complaintstatus',
        'auditstatus',
        'findingstatus',
        'documenttype',
        'documentstatus',
        'riskstatus',
        'rca_status_enum',
        'rcasstatus',
        'assignedentitytype',
        'investigationstatus',
    ]
    
    for enum_type in old_enum_types:
        op.execute(f"DROP TYPE IF EXISTS {enum_type} CASCADE;")


def downgrade() -> None:
    """This migration is not reversible - enum types would need to be recreated."""
    pass
