# 06 - Noise Filtering (Pre-LLM Property Filtering)

## Purpose

The noise filtering system reduces false positives from Azure What-If output by
removing known-noisy property-change lines from the raw What-If text **before**
the content is sent to the LLM. This is more reliable than post-LLM summary
matching because:

1. **Property names are deterministic** — `etag` always says "etag", unlike
   LLM summaries which vary in phrasing.
2. **Keywords are cross-cutting** — a single pattern like `etag` suppresses that
   property across every Azure resource type automatically.
3. **The LLM never sees the noise** — it cannot misreport a filtered property
   as a real change, so confidence scoring is more accurate.

**Files:**
- `bicep_whatif_advisor/noise_filter.py` — pre-LLM filtering engine
- `bicep_whatif_advisor/data/builtin_noise_patterns.txt` — bundled pattern set
- `bicep_whatif_advisor/cli.py` (lines ~380-410) — filtering wired before LLM call

## Problem Statement

Azure What-If output contains significant noise:
- Computed metadata fields (`etag`, `provisioningState`, `resourceGuid`)
- IPv6 platform flags (`ipv6AddressSpace`, `disableIpv6`, `enableIPv6Addressing`)
- Diagnostics noise (`logAnalyticsDestinationType`)
- Hidden Azure-managed tags (`hidden-link:`, `hidden-title`)
- Load balancer and NIC computed fields (`inboundNatRules`, `effectiveRouteTable`)

**Impact:** These properties appear as `~` (Modify) changes in What-If output,
causing the LLM to report spurious modifications and potentially failing CI gates.

## Architecture

```
Raw What-If text (stdin)
    ↓
noise_filter.py: filter_whatif_text()
    ├── Load built-in patterns (bicep_whatif_advisor/data/builtin_noise_patterns.txt)
    ├── Load user patterns (--noise-file, additive)
    ├── For each line in What-If text:
    │   ├── Is this a property-change line? (4+ space indent + change symbol)
    │   │   ├── YES → check against all patterns
    │   │   │         match → suppress line
    │   │   │         no match → keep line
    │   │   └── NO  → keep line (resource headers, info lines, etc.)
    └── Return filtered text + count of removed lines
    ↓
Cleaned What-If text → LLM (via build_user_prompt)
    ↓
LLM assigns confidence levels to remaining resources
    ↓
filter_by_confidence() splits high/low confidence resources
    ↓
Separate rendering (main table + "Potential Noise" section)
```

## Property-Change Line Detection

A line is eligible for noise filtering if:
- It has **4 or more leading spaces** (property-level indentation)
- Its first non-whitespace character is `~`, `+`, or `-` (change symbol)

This precisely targets property-change lines within Modify blocks and excludes:
- Resource-level header lines (`  ~ Microsoft.Network/...`) — only 2-space indent
- Resource attribute lines (`      id:   "..."`, `      name: "..."`) — indented but no change symbol

**Example lines and eligibility:**

```
  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]   ← resource header (2 spaces, SKIP)
      id:   "/subscriptions/..."                            ← attribute (no symbol, SKIP)
      ~ properties.etag: "old" => "new"                    ← property change (6 spaces + ~, CHECK)
      ~ properties.addressSpace.addressPrefixes[0]: ...     ← property change (6 spaces + ~, CHECK)
      + properties.ipv6AddressSpace: null => ""             ← property change (6 spaces + +, CHECK)
```

Implementation in `noise_filter.py`:

```python
_PROPERTY_INDENT_MIN = 4
_CHANGE_SYMBOLS = frozenset({"+", "-", "~"})

def _is_property_change_line(line: str) -> bool:
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    if indent < _PROPERTY_INDENT_MIN or not stripped:
        return False
    return stripped[0] in _CHANGE_SYMBOLS
```

## Pattern File Format

One pattern per line. Blank lines and lines starting with `#` are ignored.

```
# Comments start with #

# Plain text (default) — case-insensitive substring match
etag
provisioningState
ipv6AddressSpace

# regex: prefix — Python re.search(), case-insensitive
regex: properties\.metadata\..*Version

# fuzzy: prefix — legacy SequenceMatcher (--noise-threshold applies)
fuzzy: Changes to internal routing configuration
```

### Pattern Types

| Prefix | Strategy | Use Case |
|--------|----------|----------|
| *(none)* | `keyword in line.lower()` | Simple property name keywords — most common |
| `regex:` | `re.search(pattern, line, IGNORECASE)` | Complex property paths, wildcards |
| `fuzzy:` | `SequenceMatcher.ratio() >= threshold` | Legacy support; not recommended for new patterns |

**Why keyword containment is the default:**
- `"etag"` matches `"      ~ properties.etag: \"old\" => \"new\""` ✓
- `"etag"` matches `"      ~ properties.storageEtag: ..."` (acceptable — still noise)
- Short, specific property names like `etag`, `resourceGuid`, `provisioningState` are
  unlikely to appear in real infrastructure property names
- No need to know the LLM's phrasing — matching the raw What-If is deterministic

## Built-in Pattern Set

Bundled at `bicep_whatif_advisor/data/builtin_noise_patterns.txt`. Loaded
automatically on every run. Covers the most common Azure What-If noise across
all resource types:

| Pattern | Resource Types Affected |
|---------|------------------------|
| `etag` | Virtually all resources |
| `provisioningState` | Virtually all resources |
| `resourceGuid` | Networking resources |
| `creationTime`, `lastModifiedTime` | Storage, KeyVault, others |
| `logAnalyticsDestinationType` | All diagnostic settings |
| `ipv6AddressSpace` | VNets, subnets |
| `disableIpv6`, `enableIPv6Addressing`, `enableIPv6` | VNets, subnets, NICs |
| `hidden-link:`, `hidden-title`, `hidden-related:` | All resources with hidden tags |
| `inboundNatRules` | Load balancers |
| `effectiveRouteTable`, `effectiveNetworkSecurityGroup`, `appliedDnsServers` | NICs |

**Design principle:** A small, carefully chosen set covers the vast majority of
What-If noise because these properties are cross-cutting — not resource-type-specific.

## CLI Integration

### Pattern Loading (cli.py lines ~380-410)

```python
noise_patterns = []
if not no_builtin_patterns:
    noise_patterns.extend(load_builtin_patterns())
if noise_file:
    noise_patterns.extend(load_user_patterns(noise_file))

if noise_patterns:
    fuzzy_threshold = noise_threshold / 100.0
    whatif_content, num_filtered = filter_whatif_text(
        whatif_content, noise_patterns, fuzzy_threshold
    )
    if num_filtered > 0:
        sys.stderr.write(
            f"🔕 Pre-filtered {num_filtered} known-noisy property "
            f"line(s) from What-If output\n"
        )
```

This runs **before** `build_user_prompt()` — the LLM receives already-cleaned input.

### CLI Options

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--noise-file` | String | `None` | Path to additional patterns file (additive with built-ins) |
| `--noise-threshold` | Integer | `80` | Similarity % threshold for `fuzzy:` prefix patterns only |
| `--no-builtin-patterns` | Flag | `False` | Disable the bundled built-in patterns |

### User File Is Additive

Built-in patterns and user patterns are merged into a single list before
filtering. Users only need to add patterns for their project-specific noise;
they do not need to replicate the built-ins.

## Layer 2: LLM Confidence Scoring

After pre-LLM filtering removes deterministic noise, the LLM still assigns
confidence levels to each remaining resource:

| Level | Meaning |
|-------|---------|
| `high` | Real, meaningful change |
| `medium` | Potentially real but uncertain |
| `low` | Likely noise the LLM identified |

`filter_by_confidence()` in `cli.py` splits resources into high-confidence
(medium/high) and low-confidence (low) buckets for separate rendering.

The two layers are complementary:
- Pre-LLM patterns handle **known, deterministic** noise → removed before analysis
- LLM confidence handles **novel or ambiguous** noise → flagged after analysis

## Package Data Distribution

The built-in patterns file is included in the installed package via `pyproject.toml`:

```toml
[tool.setuptools.package-data]
bicep_whatif_advisor = ["data/*.txt"]
```

The file is loaded at runtime using a path relative to the module:

```python
def load_builtin_patterns() -> list:
    data_path = Path(__file__).parent / "data" / "builtin_noise_patterns.txt"
    return _load_patterns_from_path(data_path)
```

Fails gracefully (returns `[]`) if the file is missing — pre-LLM filtering is
simply skipped, and LLM confidence scoring handles noise instead.

## Example Workflow

### Input: Raw What-If Text

```
  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]
      ...
      ~ properties.etag: "W/\"abc\"" => "W/\"def\""
      ~ properties.provisioningState: "Succeeded" => "Updating"
      ~ properties.ipv6AddressSpace.addressPrefixes[0]: null => ""
      ~ properties.addressSpace.addressPrefixes[0]: "10.0.0.0/16" => "10.0.0.0/8"
```

### After filter_whatif_text() (4 patterns matched → 3 lines removed)

```
  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]
      ...
      ~ properties.addressSpace.addressPrefixes[0]: "10.0.0.0/16" => "10.0.0.0/8"
```

**LLM now sees only the real change** — address prefix expansion. It can
accurately report this as a high-confidence modification without being distracted
by etag/provisioningState/IPv6 noise.

## Testing

Use `tests/fixtures/noisy_changes.txt` — a fixture that mixes real changes
with known noisy properties:

```bash
cat tests/fixtures/noisy_changes.txt | bicep-whatif-advisor
```

With built-in patterns active, the etag/provisioningState/IPv6 lines are
stripped before the LLM call. The LLM should report only the real changes
(address prefix, RetentionInDays, DNS server) as high-confidence.

```bash
# Verify filtering is happening (watch stderr)
cat tests/fixtures/noisy_changes.txt | bicep-whatif-advisor 2>&1 | head -5

# Disable built-ins to see unfiltered LLM output
cat tests/fixtures/noisy_changes.txt | bicep-whatif-advisor --no-builtin-patterns

# Use only a custom patterns file
cat tests/fixtures/noisy_changes.txt | bicep-whatif-advisor \
  --no-builtin-patterns \
  --noise-file my-patterns.txt
```

## Future Improvements

1. **Block-level suppression** — if all property changes in a Modify block are
   filtered, suppress the entire resource block rather than sending an empty
   Modify to the LLM
2. **Resource-type-scoped patterns** — `[Microsoft.Network/virtualNetworks]`
   section headers to apply patterns only to specific resource types
3. **Pattern suggestions** — analyze `--verbose` output to recommend new patterns
   based on resources the LLM marks as low-confidence

## Next Steps

For details on related modules:
- [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) — how confidence levels are defined in prompts
- [05-OUTPUT-RENDERING.md](05-OUTPUT-RENDERING.md) — how low-confidence resources are displayed
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) — CLI flags and filtering integration
