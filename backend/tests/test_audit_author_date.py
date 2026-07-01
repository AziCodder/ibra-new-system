"""Phase 12.1 — cross-cutting audit that every user-authored record carries author + date.

Notes, ledger entries (ДиР), logistics comments and payments must each persist
who created the record (author_id) and when (created_at), and must expose both the
author's name and the timestamp in their API output. This test codifies that
unified pattern so any future record type is held to the same contract.
"""

from app.models.ledger_entry import LedgerEntry
from app.models.logistics_comment import LogisticsComment
from app.models.note import Note
from app.models.payment import Payment
from app.schemas.ledger_entry import LedgerEntryOut
from app.schemas.logistics_comment import LogisticsCommentOut
from app.schemas.note import NoteOut
from app.schemas.payment import PaymentOut

# Every audited (model, out-schema) pair that represents a user-authored record.
AUDITED = [
    (Note, NoteOut),
    (LedgerEntry, LedgerEntryOut),
    (LogisticsComment, LogisticsCommentOut),
    (Payment, PaymentOut),
]


def test_models_persist_author_and_date():
    for model, _ in AUDITED:
        columns = set(model.__table__.columns.keys())
        assert "author_id" in columns, f"{model.__name__} must persist author_id"
        assert "created_at" in columns, f"{model.__name__} must persist created_at"


def test_out_schemas_expose_author_name_and_date():
    for _, out_schema in AUDITED:
        fields = set(out_schema.model_fields)
        missing = {"author_id", "author_name", "created_at"} - fields
        assert not missing, f"{out_schema.__name__} must expose {sorted(missing)}"


def test_created_at_has_server_default():
    """created_at is set by the DB, not the caller — a trustworthy audit timestamp."""
    for model, _ in AUDITED:
        created_at = model.__table__.columns["created_at"]
        assert created_at.server_default is not None, (
            f"{model.__name__}.created_at must have a server_default"
        )
