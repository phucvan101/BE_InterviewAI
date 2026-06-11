from pydantic import BaseModel, Field


class SendEmailRequest(BaseModel):
    session_id: int = Field(..., description="ID của analysis session")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": 1
            }
        }


class SendEmailResponse(BaseModel):
    success: bool
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Email sent successfully"
            }
        }
