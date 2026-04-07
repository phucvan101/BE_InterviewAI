from pydantic import BaseModel, ConfigDict


class InterviewQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_session_id: int
    question_id: int