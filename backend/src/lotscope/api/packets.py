from datetime import date, datetime
from typing import Annotated, Literal

from arq import ArqRedis
from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_arq_pool, get_current_user, get_session
from lotscope.core.errors import NotFoundError
from lotscope.packet.models import SalePacket
from lotscope.packet.service import enqueue_packet, get_packet, list_packets

router = APIRouter(prefix="/packets", tags=["packets"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
ArqDep = Annotated[ArqRedis, Depends(get_arq_pool)]


class PacketRequest(BaseModel):
    sale_date: date


class PacketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sale_date: date
    status: Literal["pending", "ready", "failed"]
    error: str | None = None
    generated_at: datetime | None = None
    download_url: str | None = None


def _to_read(packet: SalePacket) -> PacketRead:
    read = PacketRead.model_validate(packet)
    if read.status == "ready":
        read.download_url = f"/packets/{read.id}/download"
    return read


@router.post("", response_model=PacketRead, status_code=status.HTTP_202_ACCEPTED)
async def request_packet(
    data: PacketRequest, session: SessionDep, user: CurrentUserDep, arq: ArqDep
) -> PacketRead:
    packet = await enqueue_packet(session, user.id, data.sale_date)
    await session.commit()
    await arq.enqueue_job("generate_sale_packet", packet.id)
    return _to_read(packet)


@router.get("", response_model=list[PacketRead])
async def read_own_packets(session: SessionDep, user: CurrentUserDep) -> list[PacketRead]:
    return [_to_read(packet) for packet in await list_packets(session, user.id)]


@router.get("/{packet_id}", response_model=PacketRead)
async def read_own_packet(packet_id: int, session: SessionDep, user: CurrentUserDep) -> PacketRead:
    return _to_read(await get_packet(session, packet_id, user.id))


@router.get("/{packet_id}/download")
async def download_own_packet(
    packet_id: int, session: SessionDep, user: CurrentUserDep
) -> FileResponse:
    packet = await get_packet(session, packet_id, user.id)
    if packet.status != "ready" or packet.pdf_path is None:
        raise NotFoundError(f"Packet {packet_id} is not ready to download.")
    return FileResponse(
        packet.pdf_path,
        media_type="application/pdf",
        filename=f"lotscope-sale-packet-{packet.sale_date.isoformat()}.pdf",
    )
