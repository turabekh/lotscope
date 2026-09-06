from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base


class AnalystUsage(Base):
    """One day of Analyst spend for one user, split by what is metered and what is not.

    `source` is the split. `chat` is what the buyer starts by typing in the thread, and
    it is what the per-user ceiling governs. `job` is the nightly brief and the sale
    packet, which the buyer did not ask for at that moment and which carry their own
    caps — those runs must never be the reason a buyer's next question is refused.

    Both are real money, so both are counted here: the global ceiling and the admin
    spend view read every row, and only the per-user check filters to `chat`. Splitting
    at write time is what lets one table be honest about the bill and honest about the
    ceiling at once.
    """

    __tablename__ = "analyst_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "day", "source", name="uq_analyst_usage_user_day_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    day: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False, server_default="chat")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    usd_estimate: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default="0"
    )
    runs: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
