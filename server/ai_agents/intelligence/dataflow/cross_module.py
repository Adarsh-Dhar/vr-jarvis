"""Cross-file and cross-module propagation for interprocedural analysis."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from pathlib import Path
from .models import DefUseFacts, Definition
from .interprocedural import InterproceduralSummaryBuilder, FunctionSummary


@dataclass
class ModuleSummary:
    """Summary of a module for cross-file analysis."""
    module_id: str  # File path or module name
    file_path: str
    top_level_definitions: List[str]  # Definition IDs at module level
    global_writes: List[str]  # Definitions that write to globals
    imports: List[str]  # Imported modules
    exports: List[str]  # Names exported from this module
    metadata: Dict[str, Any] = field(default_factory=dict)


class CrossModuleAnalyzer:
    """
    Analyze cross-file and cross-module data flow.

    Handles:
    - Module-level facts (top-level assignments, globals)
    - Import resolution and cross-module references
    - Global variable propagation across files
    """

    def __init__(self):
        self._module_summaries: Dict[str, ModuleSummary] = {}
        self._import_graph: Dict[str, Set[str]] = {}  # module -> set of imports

    def analyze_module(
        self,
        facts: DefUseFacts,
        file_path: str
    ) -> ModuleSummary:
        """
        Analyze a module (file) for cross-file propagation.

        Returns a ModuleSummary with top-level definitions and imports.
        """
        module_id = file_path

        # Identify top-level definitions (not inside functions)
        top_level_defs = []
        global_writes = []

        for definition in facts.definitions:
            # Assume all definitions in this facts are at module level
            # (A full implementation would track scope)
            top_level_defs.append(definition.id)

            if definition.metadata.get('is_global'):
                global_writes.append(definition.id)

        # Extract imports from operations
        imports = []
        for operation in facts.operations:
            if operation.operation == 'Import' or operation.operation == 'ImportFrom':
                imports.append(operation.expression)

        summary = ModuleSummary(
            module_id=module_id,
            file_path=file_path,
            top_level_definitions=top_level_defs,
            global_writes=global_writes,
            imports=imports,
            exports=[],  # Would need name analysis
            metadata={}
        )

        self._module_summaries[module_id] = summary
        self._import_graph[module_id] = set(imports)

        return summary

    def resolve_import(
        self,
        import_name: str,
        source_module: str
    ) -> Optional[str]:
        """
        Resolve an import to a target module.

        Returns the module ID if resolvable, None otherwise.
        """
        # Simplified import resolution
        # A full implementation would:
        # 1. Check local files
        # 2. Check installed packages
        # 3. Check Python stdlib
        return None

    def propagate_globals(
        self,
        all_summaries: Dict[str, ModuleSummary]
    ) -> Dict[str, Set[str]]:
        """
        Propagate global variable definitions across modules.

        Returns: module -> set of global definitions it uses from other modules
        """
        global_usage: Dict[str, Set[str]] = {}

        for module_id, summary in all_summaries.items():
            used_globals = set()

            # Check if this module imports from others
            for import_name in summary.imports:
                target_module = self.resolve_import(import_name, module_id)
                if target_module and target_module in all_summaries:
                    target_summary = all_summaries[target_module]
                    # All top-level defs in target are potential globals
                    used_globals.update(target_summary.top_level_definitions)

            global_usage[module_id] = used_globals

        return global_usage

    def get_module_summary(self, module_id: str) -> Optional[ModuleSummary]:
        """Get a module summary by ID."""
        return self._module_summaries.get(module_id)
