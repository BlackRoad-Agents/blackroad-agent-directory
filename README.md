# blackroad-agent-directory

Agent registry and directory for the BlackRoad system. Agent profiles, capability index, skill matching, routing rules, and availability tracking.

## Install

pip install -e .

## Usage

python src/agent_directory.py list
python src/agent_directory.py register nova NOVA --type creative --tags "creative,writing"
python src/agent_directory.py find --category security --min-prof 80
python src/agent_directory.py match "security,encryption"
python src/agent_directory.py route --task-type worker
python src/agent_directory.py update alice busy --tasks 5 --load 50

## Architecture

- SQLite: agent_profiles, capabilities, skill_matches, routing_rules, availability
- Dataclasses: AgentProfile, Capability, SkillMatch, RoutingRule, Availability
- Skill matching uses weighted proficiency scoring

## Development

pip install pytest pytest-cov flake8
pytest tests/ -v --cov=src
