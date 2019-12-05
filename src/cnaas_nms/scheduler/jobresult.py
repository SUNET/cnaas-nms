from dataclasses import dataclass

from typing import Optional


@dataclass
class JobResult(object):
    job_id: Optional[int] = None
    next_job_id: Optional[int] = None


@dataclass
class StrJobResult(JobResult):
    result: Optional[str] = None


@dataclass
class DictJobResult(JobResult):
    result: Optional[dict] = None
