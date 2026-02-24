"""
Unit tests for dependency validation.
"""

import pytest
from modules.utils.dependency_resolver import (
    DependencyGraph,
    DependencyNode,
    validate_dependencies
)


class TestDependencyValidation:
    """Test dependency validation function."""

    def test_valid_dependencies(self):
        """Test that valid dependencies pass validation."""
        # Create a simple graph
        graph = DependencyGraph()
        graph.add_node(DependencyNode("GIO", ["SYSTEM"]))
        graph.add_node(DependencyNode("SCI", ["SYSTEM", "PLL"]))
        graph.add_node(DependencyNode("CAN", ["SYSTEM", "PLL"]))

        # Create manifest
        manifest = {
            "api_catalog": {
                "GIO": {},
                "SCI": {},
                "CAN": {}
            }
        }

        # Should return no errors
        errors = validate_dependencies(graph, manifest)
        assert errors == []

    def test_missing_dependency(self):
        """Test that missing dependencies are detected."""
        # Create graph with invalid dependency
        graph = DependencyGraph()
        graph.add_node(DependencyNode("GIO", ["SYSTEM"]))
        graph.add_node(DependencyNode("SCI", ["NONEXISTENT_MODULE"]))

        manifest = {
            "api_catalog": {
                "GIO": {},
                "SCI": {}
            }
        }

        # Should detect the missing dependency
        errors = validate_dependencies(graph, manifest)
        assert len(errors) == 1
        assert "NONEXISTENT_MODULE" in errors[0]
        assert "SCI" in errors[0]

    def test_multiple_missing_dependencies(self):
        """Test that multiple missing dependencies are all detected."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode("GIO", ["MISSING1"]))
        graph.add_node(DependencyNode("SCI", ["MISSING2", "MISSING3"]))

        manifest = {
            "api_catalog": {
                "GIO": {},
                "SCI": {}
            }
        }

        errors = validate_dependencies(graph, manifest)
        assert len(errors) == 3
        error_text = " ".join(errors)
        assert "MISSING1" in error_text
        assert "MISSING2" in error_text
        assert "MISSING3" in error_text

    def test_core_modules_allowed(self):
        """Test that core system modules are always valid."""
        core_modules = ["SYSTEM", "PLL", "VIM", "PCR", "IOMM"]

        graph = DependencyGraph()
        for core in core_modules:
            graph.add_node(DependencyNode("GIO", [core]))

        # Empty manifest - core modules should still be valid
        manifest = {"api_catalog": {}}

        errors = validate_dependencies(graph, manifest)
        assert errors == []

    def test_dependency_on_self(self):
        """Test module depending on itself."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode("GIO", ["GIO"]))

        manifest = {
            "api_catalog": {
                "GIO": {}
            }
        }

        # Should be valid (module is in manifest)
        errors = validate_dependencies(graph, manifest)
        assert errors == []

    def test_empty_graph(self):
        """Test validation with empty graph."""
        graph = DependencyGraph()
        manifest = {"api_catalog": {}}

        errors = validate_dependencies(graph, manifest)
        assert errors == []

    def test_no_dependencies(self):
        """Test modules with no dependencies."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode("GIO", []))
        graph.add_node(DependencyNode("SCI", []))

        manifest = {
            "api_catalog": {
                "GIO": {},
                "SCI": {}
            }
        }

        errors = validate_dependencies(graph, manifest)
        assert errors == []

    def test_case_sensitivity(self):
        """Test that dependency names are case-sensitive."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode("GIO", ["system"]))  # lowercase

        manifest = {
            "api_catalog": {
                "GIO": {}
            }
        }

        # "system" (lowercase) should not match "SYSTEM" (uppercase)
        # But SYSTEM is a core module, so let's use a non-core module
        graph = DependencyGraph()
        graph.add_node(DependencyNode("GIO", ["sci"]))  # lowercase

        manifest = {
            "api_catalog": {
                "GIO": {},
                "SCI": {}  # uppercase in manifest
            }
        }

        errors = validate_dependencies(graph, manifest)
        # "sci" should not match "SCI"
        assert len(errors) == 1
        assert "sci" in errors[0]

    def test_missing_api_catalog(self):
        """Test validation when api_catalog is missing from manifest."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode("GIO", ["SYSTEM"]))

        manifest = {}  # No api_catalog

        # Should handle gracefully, only core modules valid
        errors = validate_dependencies(graph, manifest)
        assert errors == []  # SYSTEM is a core module

    def test_partial_manifest(self):
        """Test with some modules in manifest, some missing."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode("GIO", ["SCI"]))
        graph.add_node(DependencyNode("SCI", ["CAN"]))
        graph.add_node(DependencyNode("CAN", ["SYSTEM"]))

        manifest = {
            "api_catalog": {
                "GIO": {},
                "SCI": {}
                # CAN is missing
            }
        }

        errors = validate_dependencies(graph, manifest)
        assert len(errors) == 1
        assert "CAN" in errors[0]
        assert "SCI" in errors[0]  # SCI depends on CAN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
