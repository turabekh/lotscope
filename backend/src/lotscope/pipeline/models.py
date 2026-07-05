from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class Deal(Base, TimestampMixin):
    __tablename__ = "deal"
    __table_args__ = (UniqueConstraint("user_id", "parcel_number", name="uq_deal_user_parcel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    parcel_number: Mapped[str] = mapped_column(
        String(40), ForeignKey("parcel.parcel_number", ondelete="CASCADE")
    )
    stage: Mapped[str] = mapped_column(String(20), nullable=False, server_default="lead")
    note: Mapped[str | None] = mapped_column(Text)
    target_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
