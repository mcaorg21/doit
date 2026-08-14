from datetime import datetime

from pydantic import BaseModel


class Credential(BaseModel):
    id: str
    projectId: str
    name: str
    type: str
    """Free-form tag identifying what this credential is for (e.g. "2captcha") — lets
    a node's credential-picker field filter to only the credentials that make sense
    for it, via ParamField.credentialType."""
    value: str
    """The actual secret (API key, token, ...). Stored in plain JSON like everything
    else in data/projects/ — this app has no auth/multi-tenancy boundary to protect
    against, so encrypting it at rest wouldn't buy anything a local file wouldn't
    already need protecting some other way."""
    createdAt: datetime
    updatedAt: datetime


class CredentialCreate(BaseModel):
    name: str
    type: str
    value: str


class CredentialUpdate(BaseModel):
    name: str
    type: str
    value: str
