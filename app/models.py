from pydantic import BaseModel, Field


class ReadingIn(BaseModel):
    device_id: str
    reading_id: str
    metric: str
    value: float
    recorded_at: str = Field(..., description="ISO-8601 UTC timestamp")
