"""Minimal SQLModel-based store for recall records."""
from typing import Optional
from sqlmodel import SQLModel, Field, create_engine, Session, select
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///recalls.db")
_engine = create_engine(DATABASE_URL, echo=False)


class Recall(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recall_number: str
    reason_for_recall: Optional[str] = None
    product_description: Optional[str] = None
    recall_initiation_date: Optional[str] = None


def init_db() -> None:
    SQLModel.metadata.create_all(_engine)


def save_if_new(record: dict) -> Optional[Recall]:
    with Session(_engine) as sess:
        # naive dedupe by recall_number
        q = select(Recall).where(Recall.recall_number == record.get("recall_number"))
        existing = sess.exec(q).first()
        if existing:
            return None
        r = Recall(
            recall_number=record.get("recall_number", ""),
            reason_for_recall=record.get("reason_for_recall", ""),
            product_description=record.get("product_description", ""),
            recall_initiation_date=record.get("recall_initiation_date", ""),
        )
        sess.add(r)
        sess.commit()
        sess.refresh(r)
        return r
