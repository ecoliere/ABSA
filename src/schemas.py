from pydantic import BaseModel
from typing import List, Optional

class TopicResponse(BaseModel):
    name: str
    sentiment: str
    weight: float

class AnalyzeSingleResponse(BaseModel):
    session_id: int
    access_token: str
    text: str
    topics: List[TopicResponse]

class UploadFileResponse(BaseModel):
    session_id: int
    access_token: str
    file_name: str
    message: str

class AspectShortResponse(BaseModel):
    name: str
    total: int
    positivity: float
    negativity: float
    positive_count: int
    neutral_count: int
    negative_count: int
    sentiment_score: float
    average_score: float

class ReviewShortResponse(BaseModel):
    id: int
    text: str
    topics: str
    full_text: str

class ResultsResponse(BaseModel):
    session_id: int
    total_reviews: int
    status: str
    skip: int = 0
    limit: int = 50
    aspects: List[AspectShortResponse]
    reviews: List[ReviewShortResponse]

class ReasonGroupMember(BaseModel):
    reason: str
    count: int

class ReasonGroupResponse(BaseModel):
    name: str
    total_frequency: int
    members_with_freq: List[ReasonGroupMember]

class DeepAnalysisResponse(BaseModel):
    aspect: str
    total_mentions: int
    total_reasons: int
    average_score: float
    praised_groups: List[ReasonGroupResponse]
    criticized_groups: List[ReasonGroupResponse]
    recommendation: str

class QueueStatusResponse(BaseModel):
    queue_length: int
    workers: int
    max_concurrent: int

class DLQResponse(BaseModel):
    size: int
    samples: List[dict]

class ProcessingStatusResponse(BaseModel):
    session_id: int
    status: str
    total_reviews: int
    processed_reviews: int