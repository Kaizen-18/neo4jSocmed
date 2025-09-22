# app/schemas.py
from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4

class UserCreate(BaseModel):
    username: str
    name: Optional[str] = None
    bio: Optional[str] = None

class UserOut(BaseModel):
    id: str
    username: str
    name: Optional[str] = None
    bio: Optional[str] = None

class PostCreate(BaseModel):
    author_username: str
    content: str = Field(..., max_length=500)

class PostOut(BaseModel):
    id: str
    author_username: str
    content: str
    created_at: str

class FollowAction(BaseModel):
    follower_username: str
    followee_username: str

class LikeAction(BaseModel):
    username: str
    post_id: str
