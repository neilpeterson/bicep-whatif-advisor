"""Custom risk assessment agent loader.

Loads markdown files with YAML frontmatter from a directory and registers
them as additional RiskBucket entries in the bucket registry.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

from .buckets import RISK_BUCKETS, RiskBucket

# Built-in bucket IDs that custom agents must not collide with
BUILTIN_BUCKET_IDS = frozenset({"drift", "intent"})

# Valid characters for agent IDs: alphanumeric, hyphens, underscores
_VALID_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

_VALID_THRESHOLDS = {"low", "medium", "high"}
_VALID_DISPLAY_MODES = {"summary", "table", "list"}

# Default findings columns when no custom columns specified
DEFAULT_FINDINGS_COLUMNS = [
    {"name": "Resource", "description": "resource name from the What-If output"},
    {"name": "Issue", "description": "specific issue found"},
    {"name": "Recommendation", "description": "actionable recommendation"},
]


def _slugify(name: str) -> str:
    """Convert a column display name to a JSON-safe key.

    Lowercase, replace non-alphanumeric chars with underscores,
    collapse consecutive underscores, strip leading/trailing underscores.

    Examples:
        "SFI ID and Name" → "sfi_id_and_name"
        "Compliance Status" → "compliance_status"
    """
    key = name.lower()
    key = re.sub(r"[^a-z0-9]", "_", key)
    key = re.sub(r"_+", "_", key)
    return key.strip("_")


def _parse_frontmatter(content: str) -> Tuple[dict, str]:
    """Split markdown content into YAML frontmatter dict and body.

    Args:
        content: Full file content

    Returns:
        Tuple of (metadata_dict, body_string)

    Raises:
        ValueError: If frontmatter delimiters are missing or YAML is malformed
    """
    if not content.startswith("---"):
        raise ValueError("Agent file must start with YAML frontmatter delimiters (---)")

    # Find closing delimiter (skip the opening ---)
    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        raise ValueError("Agent file missing closing frontmatter delimiter (---)")

    yaml_block = content[4:end_idx]  # Skip "---\n"
    body = content[end_idx + 4 :]  # Skip "\n---\n" or "\n---"
    if body.startswith("\n"):
        body = body[1:]

    try:
        metadata = yaml.safe_load(yaml_block)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in frontmatter: {e}")

    if not isinstance(metadata, dict):
        raise ValueError("Frontmatter must contain YAML key-value pairs")

    return metadata, body


def parse_agent_file(file_path: Path) -> Optional[RiskBucket]:
    """Parse a markdown agent file into a RiskBucket.

    Args:
        file_path: Path to the .md agent file

    Returns:
        RiskBucket instance, or None if the agent has enabled: false

    Raises:
        ValueError: If the file is missing required fields or has invalid format
        FileNotFoundError: If the file does not exist
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Agent file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    metadata, body = _parse_frontmatter(content)

    # Validate required fields (before enabled check, so disabled agents still report their ID)
    agent_id = metadata.get("id")
    if not agent_id:
        raise ValueError(f"Agent file {file_path.name}: missing required 'id' field in frontmatter")

    # Check enabled flag (defaults to True)
    if not metadata.get("enabled", True):
        return None

    agent_id = str(agent_id)

    if not _VALID_ID_RE.match(agent_id):
        raise ValueError(
            f"Agent file {file_path.name}: id '{agent_id}'"
            f" contains invalid characters (use alphanumeric,"
            f" hyphens, underscores only)"
        )

    if agent_id in BUILTIN_BUCKET_IDS:
        raise ValueError(
            f"Agent file {file_path.name}: id '{agent_id}' collides with built-in bucket"
        )

    display_name = metadata.get("display_name")
    if not display_name:
        raise ValueError(
            f"Agent file {file_path.name}: missing required 'display_name' field in frontmatter"
        )

    # Validate optional fields
    default_threshold = str(metadata.get("default_threshold", "high")).lower()
    if default_threshold not in _VALID_THRESHOLDS:
        raise ValueError(
            f"Agent file {file_path.name}: invalid"
            f" default_threshold '{default_threshold}'"
            f" (must be low, medium, or high)"
        )

    optional = bool(metadata.get("optional", False))

    # Validate display mode
    display = str(metadata.get("display", "summary")).lower()
    if display not in _VALID_DISPLAY_MODES:
        raise ValueError(
            f"Agent file {file_path.name}: invalid"
            f" display '{display}'"
            f" (must be summary, table, or list)"
        )

    icon = str(metadata.get("icon", ""))

    # Parse custom columns
    columns = None
    raw_columns = metadata.get("columns")
    if raw_columns is not None:
        if not isinstance(raw_columns, list):
            raise ValueError(f"Agent file {file_path.name}: 'columns' must be a list of objects")
        columns = []
        seen_keys = set()
        for i, entry in enumerate(raw_columns):
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Agent file {file_path.name}: columns[{i}] must be an object with 'name'"
                )
            col_name = entry.get("name")
            if not col_name:
                raise ValueError(
                    f"Agent file {file_path.name}: columns[{i}] missing required 'name' field"
                )
            col_name = str(col_name)
            col_key = _slugify(col_name)
            if col_key in seen_keys:
                raise ValueError(
                    f"Agent file {file_path.name}: duplicate column key '{col_key}'"
                    f" (from '{col_name}')"
                )
            seen_keys.add(col_key)
            col_desc = str(entry.get("description", col_name))
            columns.append({"name": col_name, "key": col_key, "description": col_desc})

        if display not in ("table", "list") and columns:
            import warnings

            warnings.warn(
                f"Agent '{agent_id}': 'columns' specified but display is '{display}'"
                f" (columns only apply to table/list display)",
                stacklevel=2,
            )

    return RiskBucket(
        id=agent_id,
        display_name=str(display_name),
        description=f"Custom agent: {display_name}",
        prompt_instructions=body,
        optional=optional,
        default_threshold=default_threshold,
        custom=True,
        display=display,
        icon=icon,
        columns=columns,
    )


def load_agents_from_directory(
    agents_dir: str,
) -> Tuple[List[RiskBucket], List[str]]:
    """Load all .md agent files from a directory.

    Args:
        agents_dir: Path to directory containing agent .md files

    Returns:
        Tuple of (list of RiskBucket instances, list of error messages).
        Errors are non-fatal per-file issues. Successfully parsed agents
        are returned even if some files fail.
    """
    dir_path = Path(agents_dir)
    agents = []
    errors = []

    if not dir_path.exists():
        errors.append(f"Agents directory not found: {agents_dir}")
        return agents, errors

    if not dir_path.is_dir():
        errors.append(f"Agents path is not a directory: {agents_dir}")
        return agents, errors

    # Glob for .md files, sorted alphabetically for deterministic ordering
    md_files = sorted(dir_path.glob("*.md"))

    for md_file in md_files:
        try:
            agent = parse_agent_file(md_file)
            if agent is not None:
                agents.append(agent)
        except (ValueError, FileNotFoundError, UnicodeDecodeError) as e:
            errors.append(str(e))

    return agents, errors


def register_agents(agents: List[RiskBucket]) -> List[str]:
    """Register custom agents in the global RISK_BUCKETS registry.

    Validates that agent IDs don't collide with built-in buckets
    or with each other.

    Args:
        agents: List of RiskBucket instances from load_agents_from_directory

    Returns:
        List of registered agent IDs

    Raises:
        ValueError: If any agent ID collides with a built-in bucket
                    or if duplicate IDs exist among custom agents
    """
    # Check for collisions with built-in buckets
    for agent in agents:
        if agent.id in BUILTIN_BUCKET_IDS:
            raise ValueError(f"Custom agent '{agent.id}' collides with built-in bucket")

    # Check for duplicate IDs among custom agents
    seen_ids = set()
    for agent in agents:
        if agent.id in seen_ids:
            raise ValueError(f"Duplicate custom agent id: '{agent.id}'")
        seen_ids.add(agent.id)

    # Register in global registry
    registered = []
    for agent in agents:
        RISK_BUCKETS[agent.id] = agent
        registered.append(agent.id)

    return registered


def get_custom_agent_ids() -> List[str]:
    """Return list of currently registered custom agent IDs.

    Returns only custom agent IDs (not built-in drift/intent).
    """
    return [bucket_id for bucket_id, bucket in RISK_BUCKETS.items() if bucket.custom]
