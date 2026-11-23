from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from atlas.db import get_session

DB = Annotated[Session, Depends(get_session)]
