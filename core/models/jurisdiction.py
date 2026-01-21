"""Jurisdiction configuration models."""

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LegalSystemType(str, Enum):
    """Type of legal system."""

    UNITARY = "unitary"
    FEDERAL = "federal"
    DEVOLVED = "devolved"
    SUPRANATIONAL = "supranational"


class SourceType(str, Enum):
    """Type of data source."""

    OFFICIAL_GAZETTE = "official_gazette"
    CONSOLIDATED_LEGISLATION = "consolidated_legislation"
    LEGISLATION_PORTAL = "legislation_portal"
    COURT_DATABASE = "court_database"
    CASE_LAW_PORTAL = "case_law_portal"
    N_LEX_GATEWAY = "n_lex_gateway"
    ECLI_PORTAL = "ecli_portal"
    API = "api"


class AccessModel(str, Enum):
    """Access model for a source."""

    OPEN = "open"
    REGISTRATION_REQUIRED = "registration_required"
    CREDENTIALS_REQUIRED = "credentials_required"
    BLOCKED = "blocked"
    PARTIAL = "partial"


class Priority(str, Enum):
    """Task priority."""

    P0 = "p0"
    P1 = "p1"
    P2 = "p2"


class TaskStatus(str, Enum):
    """Task status."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class Source(BaseModel):
    """Data source configuration."""

    name: str
    url: str
    type: SourceType
    coverage: dict[str, Any] = Field(default_factory=dict)
    formats: list[str] = Field(default_factory=list)
    access: str = "open"
    priority: Priority = Priority.P1
    job_id: str | None = None
    notes: str | None = None


class Target(BaseModel):
    """Coverage target within the 80/20 plan."""

    source_ref: str
    scope: str
    estimated_docs: int | None = None
    priority: Priority = Priority.P0
    status: TaskStatus = TaskStatus.PLANNED
    blockers: list[str] = Field(default_factory=list)
    notes: str | None = None


class BacklogItem(BaseModel):
    """Backlog item for future work."""

    id: str
    description: str
    type: str
    depends_on: list[str] = Field(default_factory=list)
    priority: Priority = Priority.P2
    status: TaskStatus = TaskStatus.PLANNED
    github_issue: int | None = None
    notes: str | None = None


class CoveragePlan(BaseModel):
    """Coverage plan for a jurisdiction."""

    p80_legislation: dict[str, Any]
    p80_case_law: dict[str, Any]
    backlog: list[BacklogItem] = Field(default_factory=list)


class Court(BaseModel):
    """Court information."""

    name: dict[str, str]
    code: str
    ecli_code: str | None = None
    level: str | None = None
    jurisdiction_scope: str | None = None
    notes: str | None = None


class CourtStructure(BaseModel):
    """Court structure for a jurisdiction."""

    constitutional: list[Court] = Field(default_factory=list)
    supreme: list[Court] = Field(default_factory=list)
    appellate: list[Court] = Field(default_factory=list)
    administrative: list[Court] = Field(default_factory=list)
    specialized: list[Court] = Field(default_factory=list)


class JurisdictionConfig(BaseModel):
    """Complete jurisdiction configuration."""

    # Basic info
    iso_code: str
    name: dict[str, str]
    eu_member_since: str | None = None
    languages: list[str]

    # Legal system
    legal_system_type: LegalSystemType
    hierarchy_levels: list[dict[str, Any]] = Field(default_factory=list)
    court_structure: CourtStructure | None = None

    # Sources
    legislation_sources: list[Source] = Field(default_factory=list)
    case_law_sources: list[Source] = Field(default_factory=list)

    # Identifiers
    legislation_id_scheme: str | None = None
    legislation_id_patterns: list[dict[str, str]] = Field(default_factory=list)
    ecli_support: bool = False
    ecli_country_code: str | None = None
    case_law_id_patterns: list[dict[str, str]] = Field(default_factory=list)

    # Coverage
    coverage_plan: CoveragePlan | None = None

    # Access
    access_model: AccessModel = AccessModel.OPEN
    rate_limits: dict[str, Any] = Field(default_factory=dict)
    api_available: bool = False
    bulk_download: bool = False

    # Metadata
    last_updated: str | None = None
    maintainer: str | None = None
    status: str = "draft"
    notes: str | None = None

    @classmethod
    def from_yaml(cls, path: Path) -> "JurisdictionConfig":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        # Extract nested structures
        jurisdiction = data.get("jurisdiction", {})
        legal_system = data.get("legal_system", {})
        sources = data.get("sources", {})
        identifiers = data.get("identifiers", {})
        coverage = data.get("coverage_plan", {})
        access = data.get("access", {})
        metadata = data.get("metadata", {})

        # Parse sources
        legislation_sources = [
            Source(**s) for s in sources.get("legislation", [])
        ]
        case_law_sources = [
            Source(**s) for s in sources.get("case_law", [])
        ]

        # Parse backlog
        backlog_items = [
            BacklogItem(**item) for item in coverage.get("backlog", [])
        ]

        return cls(
            iso_code=jurisdiction.get("iso_code", ""),
            name=jurisdiction.get("name", {}),
            eu_member_since=jurisdiction.get("eu_member_since"),
            languages=jurisdiction.get("languages", []),
            legal_system_type=LegalSystemType(legal_system.get("type", "unitary")),
            hierarchy_levels=legal_system.get("hierarchy", {}).get("levels", []),
            legislation_sources=legislation_sources,
            case_law_sources=case_law_sources,
            legislation_id_scheme=identifiers.get("legislation", {}).get("primary_scheme"),
            legislation_id_patterns=identifiers.get("legislation", {}).get("patterns", []),
            ecli_support=identifiers.get("case_law", {}).get("ecli_support", False),
            ecli_country_code=identifiers.get("case_law", {}).get("ecli_country_code"),
            case_law_id_patterns=identifiers.get("case_law", {}).get("national_schemes", []),
            coverage_plan=CoveragePlan(
                p80_legislation=coverage.get("p80_legislation", {}),
                p80_case_law=coverage.get("p80_case_law", {}),
                backlog=backlog_items,
            ) if coverage else None,
            access_model=AccessModel(access.get("model", "open")),
            rate_limits=access.get("rate_limits", {}),
            api_available=access.get("api_available", False),
            bulk_download=access.get("bulk_download", False),
            last_updated=metadata.get("last_updated"),
            maintainer=metadata.get("maintainer"),
            status=metadata.get("status", "draft"),
            notes=metadata.get("notes"),
        )


def load_all_jurisdictions(configs_dir: Path) -> dict[str, JurisdictionConfig]:
    """Load all jurisdiction configurations."""
    configs = {}
    for yaml_file in configs_dir.glob("*.yaml"):
        try:
            config = JurisdictionConfig.from_yaml(yaml_file)
            configs[config.iso_code] = config
        except Exception as e:
            print(f"Error loading {yaml_file}: {e}")
    return configs
