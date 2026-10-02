import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Self

from fastapi import Depends, FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from caching_service import service
from caching_service.db import engine, get_session
from caching_service.models import Base, Payload


class PayloadRequest(BaseModel):
    list_1: list[str] = Field(min_length=1)
    list_2: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def lists_have_equal_length(self) -> Self:
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self


class PayloadCreated(BaseModel):
    id: uuid.UUID


class PayloadOutput(BaseModel):
    output: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Caching Service", lifespan=lifespan)

SessionDep = Annotated[Session, Depends(get_session)]


@app.post(
    "/payload",
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_200_OK: {"model": PayloadCreated, "description": "Already existed"}},
)
def create_payload(body: PayloadRequest, response: Response, session: SessionDep) -> PayloadCreated:
    payload, created = service.create_payload(session, body.list_1, body.list_2)
    if not created:
        response.status_code = status.HTTP_200_OK
    return PayloadCreated(id=payload.id)


@app.get("/payload/{payload_id}")
def read_payload(payload_id: uuid.UUID, session: SessionDep) -> PayloadOutput:
    payload = session.get(Payload, payload_id)
    if payload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payload not found")
    return PayloadOutput(output=payload.output)
