import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "install-mcp.sh"


def test_install_mcp_script_has_safe_side_effect_free_help():
    syntax = subprocess.run(
        ["bash", "-n", INSTALLER], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert syntax.returncode == 0, syntax.stderr

    help_result = subprocess.run(
        ["bash", INSTALLER, "--help"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "does not make live Jev or Laya calls" in help_result.stdout
    assert "--stop" in help_result.stdout
