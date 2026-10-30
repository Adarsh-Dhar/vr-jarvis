"""
Test Fixture Manager
Creates and manages test repositories and fixtures
"""

from pathlib import Path
from typing import Dict, Optional
import shutil
import tempfile
import yaml
import sys
sys.path.insert(0, str(Path(__file__).parent))


class TestFixtureManager:
    """Manages test fixtures and repositories"""
    
    def __init__(self, test_root: Path):
        self.test_root = test_root
        self.fixtures_dir = test_root / 'fixtures'
        self.temp_repos: Dict[str, Path] = {}
    
    def get_fixture_path(self, fixture_name: str) -> Path:
        """Get the path to a fixture"""
        fixture_path = self.fixtures_dir / fixture_name
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture {fixture_name} not found")
        return fixture_path
    
    def load_ground_truth(self, repository_name: str) -> Dict:
        """Load ground truth for a repository"""
        ground_truth_path = self.fixtures_dir / 'repositories' / repository_name / 'ground-truth.yaml'
        if not ground_truth_path.exists():
            return {}
        
        with open(ground_truth_path, 'r') as f:
            return yaml.safe_load(f)
    
    def create_temporary_repository(self, source_fixture: str) -> Path:
        """Create a temporary copy of a test repository"""
        source_path = self.get_fixture_path(f'repositories/{source_fixture}')
        temp_dir = tempfile.mkdtemp(prefix='jarvis_test_')
        temp_path = Path(temp_dir)
        
        # Copy the repository
        if source_path.is_dir():
            shutil.copytree(source_path, temp_path / source_fixture)
            repo_path = temp_path / source_fixture
        else:
            shutil.copy2(source_path, temp_path)
            repo_path = temp_path
        
        self.temp_repos[source_fixture] = temp_path
        return repo_path
    
    def cleanup_temporary_repository(self, fixture_name: str):
        """Clean up a temporary repository"""
        if fixture_name in self.temp_repos:
            temp_path = self.temp_repos[fixture_name]
            if temp_path.exists():
                shutil.rmtree(temp_path)
            del self.temp_repos[fixture_name]
    
    def cleanup_all(self):
        """Clean up all temporary repositories"""
        for fixture_name in list(self.temp_repos.keys()):
            self.cleanup_temporary_repository(fixture_name)
    
    def get_repository_fixtures(self) -> list:
        """Get list of available repository fixtures"""
        repos_dir = self.fixtures_dir / 'repositories'
        if not repos_dir.exists():
            return []
        
        return [d.name for d in repos_dir.iterdir() if d.is_dir()]
    
    def get_runtime_trace_fixtures(self) -> list:
        """Get list of available runtime trace fixtures"""
        traces_dir = self.fixtures_dir / 'runtime-traces'
        if not traces_dir.exists():
            return []
        
        return [f.name for f in traces_dir.iterdir() if f.is_file()]
