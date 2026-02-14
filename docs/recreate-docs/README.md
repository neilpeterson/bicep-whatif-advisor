# Project Recreation Documentation

This directory contains complete specifications, implementation prompts, and execution plans for recreating the `bicep-whatif-advisor` project from scratch.

## Documentation Structure

### `/specifications/`

Detailed technical specifications organized by feature:

1. **[00-OVERVIEW.md](specifications/00-OVERVIEW.md)** - Project overview and architecture
2. **[01-CLI-INPUT.md](specifications/01-CLI-INPUT.md)** - CLI framework and input validation
3. **[02-PROVIDER-SYSTEM.md](specifications/02-PROVIDER-SYSTEM.md)** - LLM provider architecture
4. **[03-PROMPT-ENGINEERING.md](specifications/03-PROMPT-ENGINEERING.md)** - Prompt construction
5. **[04-OUTPUT-RENDERING.md](specifications/04-OUTPUT-RENDERING.md)** - Output formatting
6. **[05-PLATFORM-DETECTION.md](specifications/05-PLATFORM-DETECTION.md)** - CI/CD platform auto-detection
7. **[06-RISK-ASSESSMENT.md](specifications/06-RISK-ASSESSMENT.md)** - Three-bucket risk system
8. **[07-PR-COMMENTS.md](specifications/07-PR-COMMENTS.md)** - GitHub/Azure DevOps integration
9. **[08-NOISE-FILTERING.md](specifications/08-NOISE-FILTERING.md)** - Confidence scoring and pattern matching
10. **[09-TESTING.md](specifications/09-TESTING.md)** - Test infrastructure

### `/prompts/`

Implementation prompts for AI agents to build each feature:

- `PHASE-1-CORE.md` - Core CLI, input handling, provider system
- `PHASE-2-RENDERING.md` - Output formatting and display
- `PHASE-3-CI-MODE.md` - CI/CD integration and platform detection
- `PHASE-4-RISK.md` - Risk assessment and verdict evaluation
- `PHASE-5-NOISE.md` - Noise filtering and confidence scoring
- `PHASE-6-TESTING.md` - Test suite implementation

### Implementation Plan

See [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) for the step-by-step execution plan including:
- Development phases
- Task dependencies
- Validation checkpoints
- Estimated effort per phase

## Quick Start for AI Agents

To recreate this project:

1. Read `IMPLEMENTATION-PLAN.md` to understand the execution strategy
2. Follow the phases in order (1-6)
3. Use the corresponding prompt file for each phase
4. Reference the detailed specifications as needed
5. Validate each phase before proceeding to the next

## Key Design Principles

1. **Modularity** - Each feature is independent and testable
2. **Provider Agnostic** - Pluggable LLM provider system
3. **Platform Detection** - Zero-config CI/CD integration
4. **Progressive Enhancement** - Basic mode works standalone, CI mode adds safety gates
5. **Noise Reduction** - LLM-based confidence scoring + user-defined pattern matching
6. **Three-Bucket Risk Model** - Independent evaluation of drift, intent, and operations
