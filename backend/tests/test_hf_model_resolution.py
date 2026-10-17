"""Tests for Hugging Face Hub model weight resolution and local fallback."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import torch

from ml.src.evaluate_mobilenetv3 import load_trained_mobilenetv3, resolve_checkpoint_path
from ml.src.config import MODELS_DIR


def test_resolve_checkpoint_prefers_existing_local_file():
    """Verify that an existing local file is used immediately without touching the network."""
    local_path = MODELS_DIR / "mobilenetv3_plantdisease_best.pth"
    assert local_path.exists()

    resolved = resolve_checkpoint_path(checkpoint_path=local_path)
    assert resolved == local_path


def test_resolve_checkpoint_default_local_fallback():
    """When no path is passed, default local checkpoint in ml/models/ is loaded."""
    resolved = resolve_checkpoint_path()
    assert resolved.exists()
    assert resolved.name == "mobilenetv3_plantdisease_best.pth"


def test_resolve_checkpoint_hf_hub_mocked(tmp_path):
    """When local file is missing, verify hf_hub_download is invoked with target repository."""
    fake_downloaded = tmp_path / "mocked_checkpoint.pth"
    fake_downloaded.write_text("mocked_weights")

    with patch("huggingface_hub.hf_hub_download", return_value=str(fake_downloaded)) as mock_download:
        resolved = resolve_checkpoint_path(
            checkpoint_path=tmp_path / "nonexistent_local.pth",
            repo_id="Dipxssi/krishiai-mobilenetv3",
            filename="mobilenetv3_plantdisease_best.pth",
            token="hf_mock_token",
        )

        assert resolved == fake_downloaded
        mock_download.assert_called_once_with(
            repo_id="Dipxssi/krishiai-mobilenetv3",
            filename="mobilenetv3_plantdisease_best.pth",
            token="hf_mock_token",
        )


def test_resolve_checkpoint_failure_raises_clear_error(tmp_path):
    """When both local file and HF download fail, raises clear FileNotFoundError."""
    with patch("huggingface_hub.hf_hub_download", side_effect=Exception("Repository not found")):
        with pytest.raises(FileNotFoundError) as exc_info:
            resolve_checkpoint_path(
                checkpoint_path=tmp_path / "completely_missing.pth",
                repo_id="nonexistent/repo",
            )
        assert "not found locally" in str(exc_info.value).lower()
