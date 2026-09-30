"""Limits for the single-user, 1 GB deployment; PT_* overrides YAML."""

import os
from dataclasses import dataclass, fields

from backend.app.config import load_config


@dataclass(frozen=True)
class ResourceLimits:
    cpu_threads: int = 1
    max_translation_threads: int = 1
    translation_batch_pages: int = 2
    max_pending_tasks: int = 3  # Includes the running task.
    max_upload_mb: int = 20
    max_pdf_pages: int = 200
    translation_timeout_seconds: int = 1800


def get_resource_limits() -> ResourceLimits:
    config = load_config().get("resources", {})
    values = {}
    for field in fields(ResourceLimits):
        value = int(os.environ.get(f"PT_{field.name.upper()}", config.get(field.name, field.default)))
        minimum = 0 if field.name == "translation_batch_pages" else 1
        if value < minimum:
            raise ValueError(f"resources.{field.name} 必须至少为 {minimum}")
        values[field.name] = value
    return ResourceLimits(**values)
