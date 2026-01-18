"""Add document management system tables.

Revision ID: 20260118220000
Revises: 20260118183140
Create Date: 2026-01-18 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260118220000'
down_revision: Union[str, None] = 'convert_enums_varchar'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create document management tables."""
    
    # Documents table
    op.create_table('documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('reference_number', sa.String(50), nullable=True),
        sa.Column('title', sa.String(500), nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        
        # File info
        sa.Column('file_name', sa.String(500), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(1000), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        
        # Classification
        sa.Column('document_type', sa.String(50), default='other'),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('sensitivity', sa.String(50), default='internal'),
        
        # Status
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('reviewed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        
        # Version control
        sa.Column('version', sa.String(20), default='1.0'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_latest', sa.Boolean(), default=True),
        sa.Column('parent_document_id', sa.Integer(), sa.ForeignKey('documents.id'), nullable=True),
        
        # AI metadata
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('ai_tags', sa.JSON(), nullable=True),
        sa.Column('ai_keywords', sa.JSON(), nullable=True),
        sa.Column('ai_topics', sa.JSON(), nullable=True),
        sa.Column('ai_entities', sa.JSON(), nullable=True),
        sa.Column('ai_confidence', sa.Float(), nullable=True),
        sa.Column('ai_processed_at', sa.DateTime(timezone=True), nullable=True),
        
        # Document structure
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('sheet_count', sa.Integer(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('has_images', sa.Boolean(), default=False),
        sa.Column('has_tables', sa.Boolean(), default=False),
        sa.Column('thumbnail_path', sa.String(1000), nullable=True),
        
        # Indexing
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=True),
        sa.Column('indexing_error', sa.Text(), nullable=True),
        sa.Column('vector_namespace', sa.String(100), nullable=True),
        
        # Governance dates
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True),
        
        # Access control
        sa.Column('is_public', sa.Boolean(), default=False),
        sa.Column('restricted_to_roles', sa.JSON(), nullable=True),
        sa.Column('restricted_to_departments', sa.JSON(), nullable=True),
        
        # Analytics
        sa.Column('view_count', sa.Integer(), default=0),
        sa.Column('download_count', sa.Integer(), default=0),
        sa.Column('citation_count', sa.Integer(), default=0),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        
        # Module links
        sa.Column('linked_policy_id', sa.Integer(), nullable=True),
        sa.Column('linked_standard_id', sa.Integer(), nullable=True),
        
        # Ownership
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_documents_reference_number', 'documents', ['reference_number'])
    op.create_index('ix_documents_status', 'documents', ['status'])
    op.create_index('ix_documents_document_type', 'documents', ['document_type'])
    
    # Document chunks table
    op.create_table('document_chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('heading', sa.String(500), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('section_id', sa.String(100), nullable=True),
        sa.Column('sheet_name', sa.String(100), nullable=True),
        sa.Column('char_start', sa.Integer(), nullable=True),
        sa.Column('char_end', sa.Integer(), nullable=True),
        sa.Column('vector_id', sa.String(100), nullable=True),
        sa.Column('embedding_model', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
    
    # Document annotations table
    op.create_table('document_annotations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('section_id', sa.String(100), nullable=True),
        sa.Column('sheet_name', sa.String(100), nullable=True),
        sa.Column('highlight_text', sa.Text(), nullable=True),
        sa.Column('annotation_text', sa.Text(), nullable=False),
        sa.Column('color', sa.String(20), default='yellow'),
        sa.Column('is_shared', sa.Boolean(), default=False),
        sa.Column('annotation_type', sa.String(50), default='note'),
        sa.Column('status', sa.String(50), default='open'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_annotations_document_id', 'document_annotations', ['document_id'])
    
    # Document versions table
    op.create_table('document_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.String(20), nullable=False),
        sa.Column('change_notes', sa.Text(), nullable=True),
        sa.Column('file_name', sa.String(500), nullable=False),
        sa.Column('file_path', sa.String(1000), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_versions_document_id', 'document_versions', ['document_id'])
    
    # Index jobs table
    op.create_table('index_jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('document_ids', sa.JSON(), nullable=False),
        sa.Column('chunk_count', sa.Integer(), default=0),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('chunks_processed', sa.Integer(), default=0),
        sa.Column('chunks_succeeded', sa.Integer(), default=0),
        sa.Column('chunks_failed', sa.Integer(), default=0),
        sa.Column('error_log', sa.JSON(), nullable=True),
        sa.Column('previous_vector_ids', sa.JSON(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_index_jobs_status', 'index_jobs', ['status'])
    
    # Document search logs table
    op.create_table('document_search_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('query_type', sa.String(50), default='semantic'),
        sa.Column('result_count', sa.Integer(), default=0),
        sa.Column('result_document_ids', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('was_helpful', sa.Boolean(), nullable=True),
        sa.Column('clicked_document_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_search_logs_user_id', 'document_search_logs', ['user_id'])


def downgrade() -> None:
    """Drop document management tables."""
    op.drop_table('document_search_logs')
    op.drop_table('index_jobs')
    op.drop_table('document_versions')
    op.drop_table('document_annotations')
    op.drop_table('document_chunks')
    op.drop_table('documents')
