#!/usr/bin/env python3
"""
Fixture Manager
Manages test fixtures including repositories and scenarios
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional


class FixtureManager:
    """Manages test fixtures for agent evaluation."""

    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = fixtures_dir
        self.repositories_dir = fixtures_dir / 'repositories'
        self.bug_scenarios_dir = fixtures_dir / 'bug-scenarios'
        self.conversation_scenarios_dir = fixtures_dir / 'conversation-scenarios'
        self.multi_agent_scenarios_dir = fixtures_dir / 'multi-agent-scenarios'

    def load_repository_fixture(self, fixture_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a repository fixture.

        Args:
            fixture_name: Name of the repository fixture

        Returns:
            Fixture data or None if not found
        """
        fixture_path = self.repositories_dir / fixture_name / 'fixture.yaml'
        if not fixture_path.exists():
            return None

        with open(fixture_path) as f:
            return yaml.safe_load(f)



    def load_bug_scenario_fixture(self, fixture_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a bug scenario fixture.

        Args:
            fixture_name: Name of the bug scenario fixture

        Returns:
            Fixture data or None if not found
        """
        fixture_path = self.bug_scenarios_dir / f'{fixture_name}.yaml'
        if not fixture_path.exists():
            return None

        with open(fixture_path) as f:
            return yaml.safe_load(f)

    def load_conversation_scenario_fixture(self, fixture_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a conversation scenario fixture.

        Args:
            fixture_name: Name of the conversation scenario fixture

        Returns:
            Fixture data or None if not found
        """
        fixture_path = self.conversation_scenarios_dir / f'{fixture_name}.yaml'
        if not fixture_path.exists():
            return None

        with open(fixture_path) as f:
            return yaml.safe_load(f)

    def load_multi_agent_scenario_fixture(self, fixture_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a multi-agent scenario fixture.

        Args:
            fixture_name: Name of the multi-agent scenario fixture

        Returns:
            Fixture data or None if not found
        """
        fixture_path = self.multi_agent_scenarios_dir / f'{fixture_name}.yaml'
        if not fixture_path.exists():
            return None

        with open(fixture_path) as f:
            return yaml.safe_load(f)

    def list_repository_fixtures(self) -> List[str]:
        """List all available repository fixtures."""
        if not self.repositories_dir.exists():
            return []
        return [d.name for d in self.repositories_dir.iterdir() if d.is_dir()]



    def validate_fixture(self, fixture_data: Dict[str, Any], fixture_type: str) -> bool:
        """
        Validate a fixture has required fields.

        Args:
            fixture_data: Fixture data to validate
            fixture_type: Type of fixture (repository, bug, conversation, multi_agent)

        Returns:
            True if valid, False otherwise
        """
        required_fields = {
            'repository': ['name', 'description', 'languages', 'ground_truth'],
            'bug': ['name', 'description', 'root_cause', 'expected_fix'],
            'conversation': ['name', 'description', 'messages'],
            'multi_agent': ['name', 'description', 'agents', 'expected_sequence']
        }

        if fixture_type not in required_fields:
            return False

        for field in required_fields[fixture_type]:
            if field not in fixture_data:
                return False

        return True


class FixtureRegistry:
    """Registry of all available fixtures with metadata."""

    def __init__(self, fixture_manager: FixtureManager):
        self.fixture_manager = fixture_manager
        self.registry = {
            'repositories': {},
            'bug_scenarios': {},
            'conversation_scenarios': {},
            'multi_agent_scenarios': {}
        }
        self.build_registry()

    def build_registry(self):
        """Build the fixture registry by scanning all fixture directories."""
        # Repository fixtures
        for repo_name in self.fixture_manager.list_repository_fixtures():
            fixture = self.fixture_manager.load_repository_fixture(repo_name)
            if fixture:
                self.registry['repositories'][repo_name] = {
                    'name': fixture.get('name'),
                    'description': fixture.get('description'),
                    'languages': fixture.get('languages', []),
                    'has_ground_truth': 'ground_truth' in fixture
                }

        # Bug scenario fixtures
        for bug_name in self.fixture_manager.list_repository_fixtures():  # Placeholder
            if self.fixture_manager.bug_scenarios_dir.exists():
                for f in self.fixture_manager.bug_scenarios_dir.glob('*.yaml'):
                    fixture = self.fixture_manager.load_bug_scenario_fixture(f.stem)
                    if fixture:
                        self.registry['bug_scenarios'][f.stem] = {
                            'name': fixture.get('name'),
                            'description': fixture.get('description'),
                            'root_cause': fixture.get('root_cause')
                        }

    def get_fixture_by_tag(self, tag: str) -> List[str]:
        """
        Get fixtures that match a tag.

        Args:
            tag: Tag to search for (e.g., 'python', 'sql_injection')

        Returns:
            List of fixture names matching the tag
        """
        matching_fixtures = []

        # Search in repositories
        for name, meta in self.registry['repositories'].items():
            if tag in meta.get('languages', []):
                matching_fixtures.append(f'repository:{name}')

        return matching_fixtures

    def to_dict(self) -> Dict[str, Any]:
        """Convert the registry to a dictionary."""
        return self.registry
