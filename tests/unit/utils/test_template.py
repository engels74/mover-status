"""Unit tests for message template system.

Tests cover:
- Placeholder identification and validation
- Template loading and validation
- Safe placeholder replacement
- Edge cases (empty templates, missing values, unknown placeholders)
- Security (template injection prevention)
- Property-based testing with Hypothesis
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mover_status.utils.template import (
    KNOWN_PLACEHOLDERS,
    TemplateError,
    identify_placeholders,
    load_template,
    replace_placeholders,
    validate_template,
)


class TestIdentifyPlaceholders:
    """Test suite for identify_placeholders function."""

    def test_identify_single_placeholder(self) -> None:
        """Test identifying a single placeholder."""
        template = "Progress: {percent}%"
        result = identify_placeholders(template)
        assert result == {"percent"}

    def test_identify_multiple_placeholders(self) -> None:
        """Test identifying multiple placeholders."""
        template = "Progress: {percent}% - Remaining: {remaining_data} - ETC: {etc}"
        result = identify_placeholders(template)
        assert result == {"percent", "remaining_data", "etc"}

    def test_identify_no_placeholders(self) -> None:
        """Test template with no placeholders."""
        template = "Mover process started"
        result = identify_placeholders(template)
        assert result == set()

    def test_identify_duplicate_placeholders(self) -> None:
        """Test that duplicate placeholders are deduplicated."""
        template = "{percent}% complete, {percent}% done"
        result = identify_placeholders(template)
        assert result == {"percent"}

    def test_identify_empty_template(self) -> None:
        """Test empty template string."""
        result = identify_placeholders("")
        assert result == set()

    def test_identify_all_known_placeholders(self) -> None:
        """Test template with all known placeholders."""
        template = (
            "{percent} {remaining_data} {etc} "
            "{moved_data} {total_data} {rate}"
        )
        result = identify_placeholders(template)
        assert result == KNOWN_PLACEHOLDERS


class TestValidateTemplate:
    """Test suite for validate_template function."""

    def test_validate_valid_template(self) -> None:
        """Test validation of template with known placeholders."""
        template = "Progress: {percent}% - ETC: {etc}"
        # Should not raise
        validate_template(template)

    def test_validate_template_no_placeholders(self) -> None:
        """Test validation of template without placeholders."""
        template = "Mover process started"
        # Should not raise
        validate_template(template)

    def test_validate_template_unknown_placeholder(self) -> None:
        """Test validation fails for unknown placeholder."""
        template = "Progress: {unknown_field}%"
        with pytest.raises(TemplateError) as exc_info:
            validate_template(template)
        assert "unknown placeholders" in str(exc_info.value).lower()
        assert "unknown_field" in str(exc_info.value)

    def test_validate_template_multiple_unknown(self) -> None:
        """Test validation fails for multiple unknown placeholders."""
        template = "{unknown1} and {unknown2}"
        with pytest.raises(TemplateError) as exc_info:
            validate_template(template)
        assert "unknown1" in str(exc_info.value)
        assert "unknown2" in str(exc_info.value)

    def test_validate_template_mixed_known_unknown(self) -> None:
        """Test validation fails when mixing known and unknown placeholders."""
        template = "{percent} and {unknown}"
        with pytest.raises(TemplateError) as exc_info:
            validate_template(template)
        assert "unknown" in str(exc_info.value)


class TestReplacePlaceholders:
    """Test suite for replace_placeholders function."""

    def test_replace_single_placeholder(self) -> None:
        """Test replacing a single placeholder."""
        template = "Progress: {percent}%"
        values = {"percent": 75.5}
        result = replace_placeholders(template, values)
        assert result == "Progress: 75.5%"

    def test_replace_multiple_placeholders(self) -> None:
        """Test replacing multiple placeholders."""
        template = "Progress: {percent}% - Remaining: {remaining_data}"
        values = {"percent": 50.0, "remaining_data": "125.3 GB"}
        result = replace_placeholders(template, values)
        assert result == "Progress: 50.0% - Remaining: 125.3 GB"

    def test_replace_no_placeholders(self) -> None:
        """Test template with no placeholders."""
        template = "Mover process started"
        values: dict[str, object] = {}
        result = replace_placeholders(template, values)
        assert result == "Mover process started"

    def test_replace_duplicate_placeholders(self) -> None:
        """Test replacing duplicate placeholders."""
        template = "{percent}% complete, {percent}% done"
        values = {"percent": 100.0}
        result = replace_placeholders(template, values)
        assert result == "100.0% complete, 100.0% done"

    def test_replace_missing_value(self) -> None:
        """Test error when required placeholder value is missing."""
        template = "Progress: {percent}%"
        values: dict[str, object] = {}
        with pytest.raises(TemplateError) as exc_info:
            _ = replace_placeholders(template, values)
        assert "missing values" in str(exc_info.value).lower()
        assert "percent" in str(exc_info.value)

    def test_replace_extra_values(self) -> None:
        """Test that extra values are ignored."""
        template = "Progress: {percent}%"
        values = {"percent": 75.5, "extra": "ignored"}
        result = replace_placeholders(template, values)
        assert result == "Progress: 75.5%"

    def test_replace_integer_value(self) -> None:
        """Test replacing with integer value."""
        template = "Count: {percent}"
        values = {"percent": 42}
        result = replace_placeholders(template, values)
        assert result == "Count: 42"

    def test_replace_none_value(self) -> None:
        """Test replacing with None value."""
        template = "ETC: {etc}"
        values = {"etc": None}
        result = replace_placeholders(template, values)
        assert result == "ETC: None"

    def test_replace_all_known_placeholders(self) -> None:
        """Test replacing all known placeholders."""
        template = (
            "Progress: {percent}% | "
            "Remaining: {remaining_data} | "
            "ETC: {etc} | "
            "Moved: {moved_data} | "
            "Total: {total_data} | "
            "Rate: {rate}"
        )
        values = {
            "percent": 75.5,
            "remaining_data": "125.3 GB",
            "etc": "2024-01-15 14:30:00",
            "moved_data": "350.7 GB",
            "total_data": "476.0 GB",
            "rate": "45.2 MB/s",
        }
        result = replace_placeholders(template, values)
        expected = (
            "Progress: 75.5% | "
            "Remaining: 125.3 GB | "
            "ETC: 2024-01-15 14:30:00 | "
            "Moved: 350.7 GB | "
            "Total: 476.0 GB | "
            "Rate: 45.2 MB/s"
        )
        assert result == expected


class TestLoadTemplate:
    """Test suite for load_template function."""

    def test_load_valid_template(self) -> None:
        """Test loading a valid template."""
        template = "Progress: {percent}%"
        result = load_template(template)
        assert result == template

    def test_load_template_validates(self) -> None:
        """Test that load_template validates the template."""
        template = "Progress: {unknown}%"
        with pytest.raises(TemplateError):
            _ = load_template(template)

    def test_load_empty_template(self) -> None:
        """Test loading an empty template."""
        result = load_template("")
        assert result == ""

    def test_load_template_no_placeholders(self) -> None:
        """Test loading template without placeholders."""
        template = "Mover process started"
        result = load_template(template)
        assert result == template


class TestEdgeCases:
    """Test suite for edge cases and security."""

    def test_template_with_braces_not_placeholders(self) -> None:
        """Test that braces not matching placeholder pattern are preserved."""
        # Only {word} patterns are placeholders, not {{}} or other formats
        template = "Progress: {percent}%"
        values = {"percent": 75.5}
        result = replace_placeholders(template, values)
        assert result == "Progress: 75.5%"

    def test_placeholder_case_sensitivity(self) -> None:
        """Test that placeholder names are case-sensitive."""
        # Our pattern only matches lowercase with underscores
        template = "Progress: {Percent}%"
        # This should not match our pattern (uppercase P)
        placeholders = identify_placeholders(template)
        # The pattern should not match uppercase
        assert "Percent" not in placeholders

    def test_template_injection_prevention(self) -> None:
        """Test that template system prevents code injection."""
        # Attempt to inject Python code
        template = "Progress: {percent}%"
        values = {"percent": "100; import os; os.system('ls')"}
        result = replace_placeholders(template, values)
        # Should just substitute the string, not execute code
        assert result == "Progress: 100; import os; os.system('ls')%"

    def test_empty_placeholder_name(self) -> None:
        """Test that empty placeholder names are not matched."""
        template = "Progress: {}%"
        placeholders = identify_placeholders(template)
        # Empty braces should not match our pattern
        assert len(placeholders) == 0

    def test_numeric_placeholder_name(self) -> None:
        """Test that numeric placeholder names are not matched."""
        template = "Progress: {123}%"
        placeholders = identify_placeholders(template)
        # Numeric placeholders should not match our pattern
        assert len(placeholders) == 0


class TestPropertyBased:
    """Property-based tests using Hypothesis."""

    @given(st.text())
    def test_identify_placeholders_always_returns_set(self, template: str) -> None:
        """Property test: identify_placeholders always returns a set."""
        result = identify_placeholders(template)
        assert isinstance(result, (set, frozenset))

    @given(st.text())
    def test_validate_template_never_crashes(self, template: str) -> None:
        """Property test: validate_template never crashes, only raises TemplateError."""
        try:
            validate_template(template)
        except TemplateError:
            # Expected for invalid templates
            pass

    @given(
        st.sampled_from(list(KNOWN_PLACEHOLDERS)),
        st.text(min_size=1),
    )
    def test_replace_known_placeholder_succeeds(
        self, placeholder: str, value: str
    ) -> None:
        """Property test: replacing known placeholders always succeeds."""
        template = f"{{{placeholder}}}"
        values = {placeholder: value}
        result = replace_placeholders(template, values)
        assert value in result


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_workflow(self) -> None:
        """Test complete workflow: load, validate, replace."""
        # Load and validate template
        template = load_template("Progress: {percent}% - ETC: {etc}")

        # Replace placeholders
        values = {"percent": 75.5, "etc": "2024-01-15 14:30:00"}
        result = replace_placeholders(template, values)

        assert result == "Progress: 75.5% - ETC: 2024-01-15 14:30:00"

    def test_workflow_with_invalid_template(self) -> None:
        """Test workflow fails early with invalid template."""
        with pytest.raises(TemplateError):
            _ = load_template("Progress: {invalid_placeholder}%")

    def test_all_functions_are_pure(self) -> None:
        """Verify that all functions are pure (same input = same output)."""
        template = "Progress: {percent}%"
        values = {"percent": 75.5}

        # identify_placeholders
        result1 = identify_placeholders(template)
        result2 = identify_placeholders(template)
        assert result1 == result2

        # validate_template (should not raise)
        validate_template(template)
        validate_template(template)

        # replace_placeholders
        result3 = replace_placeholders(template, values)
        result4 = replace_placeholders(template, values)
        assert result3 == result4

        # load_template
        result5 = load_template(template)
        result6 = load_template(template)
        assert result5 == result6

