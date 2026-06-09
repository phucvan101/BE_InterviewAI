# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ConversationMessageBase(BaseModel):
    role: str
    content: str
    question: Optional[str] = None
    answer: Optional[str] = None


class ConversationMessageCreate(ConversationMessageBase):
    pass


class ConversationMessageResponse(ConversationMessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    created_at: datetime
