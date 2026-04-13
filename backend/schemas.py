from pydantic import BaseModel, EmailStr
from typing import List, Optional
import datetime

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str
    education: Optional[str] = None

class UserResponse(UserBase):
    id: int
    education: Optional[str] = None
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    education: Optional[str] = None
    created_at: Optional[datetime.datetime] = None

class UserStats(BaseModel):
    simulationsStarted: int
    hoursLearned: float
    badgesEarned: int

class UserMeResponse(UserResponse):
    stats: UserStats

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str
    new_password: str

class GoogleAuthRequest(BaseModel):
    token: str

# Job/Task Schemas
class TaskBase(BaseModel):
    id: str
    level: str
    number: int
    title: str
    description: str
    initial_code: Optional[str] = None
    duration: int = 30
    hint: Optional[str] = None

class JobBase(BaseModel):
    id: str
    title: str
    description: str
    category: str
    image_url: Optional[str] = None
    participant_count: int = 0
    is_wishlisted: bool = False
    is_upcoming: bool = False
    skills: List[str] = []
    tasks: List[TaskBase] = []

    class Config:
        from_attributes = True

# Submission Schemas
class SubmissionCreate(BaseModel):
    task_id: str
    content: str

class SubmissionResponse(BaseModel):
    id: int
    task_id: str
    score: int
    feedback: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class SubmissionHistory(BaseModel):
    id: int
    task_id: str
    task_title: str
    job_title: str
    date: str
    status: str
    score: int

    class Config:
        from_attributes = True

# Notification Schemas
class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    read: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class NotificationUpdate(BaseModel):
    read: bool
