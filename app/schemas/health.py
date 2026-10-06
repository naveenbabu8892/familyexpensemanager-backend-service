from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str = Field(..., description="Application health status", examples=["healthy"])
    app_name: str = Field(..., description="Name of the service")
    version: str = Field(..., description="Service version")
    environment: str = Field(..., description="Running environment")
    database: str = Field(..., description="Database connectivity status", examples=["connected", "disconnected"])


class ErrorResponse(BaseModel):
    """Standardized error response schema."""
    success: bool = False
    error: dict
