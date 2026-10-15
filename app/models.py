from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class ReadingIn(BaseModel):
    device_id: str
    reading_id: str
    metric: str
    value: float
    recorded_at: datetime = Field(..., description="ISO-8601 UTC timestamp")

    @field_validator("recorded_at")
    @classmethod
    def _assume_utc_if_naive(cls, v: datetime) -> datetime:
        # A timestamp with no offset is taken to be UTC, as before.
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
