"""Tests for utils module."""

from pathlib import Path

from pp_doclayout.utils import (
    ensure_dir,
    get_output_dir,
    get_project_dir,
    find_image_file,
)
from pp_doclayout.config import Settings


def test_ensure_dir(tmp_path):
    """Test ensure_dir creates directory."""
    test_dir = tmp_path / "test"
    result = ensure_dir(test_dir)
    assert result.exists()
    assert result == test_dir


def test_ensure_dir_existing(tmp_path):
    """Test ensure_dir handles existing directory."""
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()
    result = ensure_dir(existing_dir)
    assert result.exists()
    assert result == existing_dir


def test_get_output_dir():
    """Test get_output_dir returns correct path."""
    output_dir = get_output_dir()
    assert isinstance(output_dir, Path)
    assert str(output_dir) == "output"


def test_get_project_dir():
    """Test get_project_dir returns correct path."""
    project_dir = get_project_dir("test.pdf")
    assert project_dir.name == "test"
    assert project_dir.parent.name == "output"


def test_get_project_dir_without_extension():
    """Test get_project_dir handles name without .pdf."""
    project_dir = get_project_dir("mypaper")
    assert project_dir.name == "mypaper"


def test_find_image_file(tmp_path):
    """Test find_image_file finds correct image."""
    # Create test directory structure - imgs and output should be siblings
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    imgs_dir = project_dir / "imgs"
    imgs_dir.mkdir()

    # Create test image file
    img_file = imgs_dir / "img_in_image_box_100_200_300_400.jpg"
    img_file.write_bytes(b"fake image data")

    # Test find_image_file
    result = find_image_file(
        imgs_dir, project_dir, bbox=[100, 200, 300, 400], label="image"
    )

    assert result is not None
    assert "img_in_image_box_100_200_300_400.jpg" in result


def test_find_image_file_not_found(tmp_path):
    """Test find_image_file returns None when image not found."""
    imgs_dir = tmp_path / "imgs"
    imgs_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    result = find_image_file(
        imgs_dir, output_dir, bbox=[999, 999, 1000, 1000], label="image"
    )

    assert result is None
