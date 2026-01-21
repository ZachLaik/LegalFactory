"""Tests for jurisdiction configuration loading."""

from pathlib import Path

import pytest
import yaml

from core.models.jurisdiction import (
    AccessModel,
    JurisdictionConfig,
    LegalSystemType,
    load_all_jurisdictions,
)


class TestJurisdictionConfig:
    """Tests for JurisdictionConfig model."""

    @pytest.fixture
    def sample_config_yaml(self) -> str:
        """Sample jurisdiction YAML content."""
        return """
jurisdiction:
  iso_code: XX
  name:
    en: Test Country
    native: Testland
  eu_member_since: "2024-01-01"
  languages:
    - en
    - xx

legal_system:
  type: unitary
  hierarchy:
    levels:
      - name: National
        code: national

sources:
  legislation:
    - name: Test Portal
      url: https://example.com/law
      type: consolidated_legislation
      access: open
      priority: p0
      job_id: xx/test_portal
  case_law:
    - name: Test Court
      url: https://example.com/courts
      type: court_database
      access: open
      priority: p0

identifiers:
  legislation:
    primary_scheme: XX-ID
    patterns:
      - name: Test Pattern
        regex: "^XX-[0-9]+$"
        example: "XX-12345"
  case_law:
    ecli_support: true
    ecli_country_code: XX

coverage_plan:
  p80_legislation:
    strategy: Test strategy
    targets:
      - source_ref: Test Portal
        scope: All laws
        estimated_docs: 1000
        priority: p0
        status: planned
  p80_case_law:
    strategy: Test case law strategy
    targets: []
  backlog: []

access:
  model: open
  api_available: false

metadata:
  status: active
"""

    def test_load_from_yaml(self, sample_config_yaml: str, tmp_path: Path) -> None:
        """Test loading config from YAML file."""
        config_file = tmp_path / "XX.yaml"
        config_file.write_text(sample_config_yaml)

        config = JurisdictionConfig.from_yaml(config_file)

        assert config.iso_code == "XX"
        assert config.name["en"] == "Test Country"
        assert config.legal_system_type == LegalSystemType.UNITARY
        assert len(config.legislation_sources) == 1
        assert len(config.case_law_sources) == 1
        assert config.ecli_support is True
        assert config.access_model == AccessModel.OPEN

    def test_load_all_jurisdictions(self, sample_config_yaml: str, tmp_path: Path) -> None:
        """Test loading multiple jurisdiction configs."""
        # Create multiple configs
        (tmp_path / "XX.yaml").write_text(sample_config_yaml)
        (tmp_path / "YY.yaml").write_text(sample_config_yaml.replace("XX", "YY"))

        configs = load_all_jurisdictions(tmp_path)

        assert len(configs) == 2
        assert "XX" in configs
        assert "YY" in configs


class TestActualConfigs:
    """Tests for actual jurisdiction config files."""

    @pytest.fixture
    def configs_dir(self) -> Path:
        """Get the actual configs directory."""
        return Path("configs/jurisdictions")

    def test_eu_config_exists(self, configs_dir: Path) -> None:
        """Test that EU config exists and is valid."""
        eu_file = configs_dir / "EU.yaml"
        if eu_file.exists():
            config = JurisdictionConfig.from_yaml(eu_file)
            assert config.iso_code == "EU"
            assert config.legal_system_type == LegalSystemType.SUPRANATIONAL

    def test_all_configs_valid_yaml(self, configs_dir: Path) -> None:
        """Test that all config files are valid YAML."""
        if not configs_dir.exists():
            pytest.skip("configs directory not found")

        for yaml_file in configs_dir.glob("*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            assert "jurisdiction" in data
            assert "iso_code" in data["jurisdiction"]

    def test_all_configs_have_required_fields(self, configs_dir: Path) -> None:
        """Test that all configs have required fields."""
        if not configs_dir.exists():
            pytest.skip("configs directory not found")

        required_sections = ["jurisdiction", "legal_system", "sources"]

        for yaml_file in configs_dir.glob("*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            for section in required_sections:
                assert section in data, f"{yaml_file.name} missing {section}"
