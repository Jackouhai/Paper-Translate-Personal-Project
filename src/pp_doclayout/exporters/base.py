"""Base exporter interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pp_doclayout.types import ProjectData


class BaseExporter(ABC):
    """Base class for document exporters."""

    @abstractmethod
    def export(
        self,
        project_data: "ProjectData",
        output_path: Path,
    ) -> Path:
        """
        Export project data to file.

        Args:
            project_data: Project data with pages and metadata
            output_path: Path to output file

        Returns:
            Path to the exported file
        """
        pass
