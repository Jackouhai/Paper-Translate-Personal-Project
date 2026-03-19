"""HTML exporter with Jinja2 templates."""

from pathlib import Path
from typing import TYPE_CHECKING
from jinja2 import Environment, FileSystemLoader

from .base import BaseExporter

if TYPE_CHECKING:
    from pp_doclayout.types import ProjectData


class HTMLExporter(BaseExporter):
    """Export project data to HTML."""

    def __init__(self, templates_dir: Path | None = None):
        """Initialize HTMLExporter.

        Args:
            templates_dir: Path to templates directory (default: src/pp_doclayout/templates)
        """
        if templates_dir is None:
            from pp_doclayout import __file__ as base_file
            templates_dir = Path(base_file).parent / "templates"

        self.templates_dir = Path(templates_dir)
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=False,
        )

    def export(
        self,
        project_data: "ProjectData",
        output_path: Path,
    ) -> Path:
        """Export project data to HTML file.

        Args:
            project_data: Project data with pages and metadata
            output_path: Path to output HTML file

        Returns:
            Path to the exported HTML file
        """
        # Load templates
        base_template = self.env.get_template("base.html")
        page_template = self.env.get_template("page.html")

        # Load style and mathjax components
        styles = (self.templates_dir / "styles.html").read_text(encoding="utf-8")
        mathjax_config = (
            self.templates_dir / "mathjax_config.html"
        ).read_text(encoding="utf-8")
        dynamic_font_size = (
            self.templates_dir / "dynamic_font_size.html"
        ).read_text(encoding="utf-8")

        # Render pages
        pages_html = ""
        for page in project_data["pages"]:
            page_html = page_template.render(
                page_number=page["page_index"],
                blocks_html=page.get("html_content", ""),
            )
            pages_html += page_html

        # Render full document
        full_html = base_template.render(
            title=f"Bản dịch {project_data['project_name']}",
            styles=styles,
            mathjax_config=mathjax_config,
            dynamic_font_size= dynamic_font_size,
            content=pages_html,
        )

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(full_html, encoding="utf-8")

        return output_path
