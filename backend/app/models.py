from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    CREATED = "created"
    UPLOADED = "uploaded"
    EXTRACTING_STROKES = "extracting_strokes"
    STROKE_READY = "stroke_ready"
    ASSIGNED_TO_WORKER = "assigned_to_worker"
    DRAWING_IN_GOODNOTES = "drawing_in_goodnotes"
    COPYING_FROM_GOODNOTES = "copying_from_goodnotes"
    UPLOADING_BINARY = "uploading_binary"
    BIN_READY = "bin_ready"
    DELIVERED = "delivered"
    FAILED = "failed"


GOODNOTES_PASTEBOARD_TYPE = "com.goodnotesapp.goodnotes5.notes"

