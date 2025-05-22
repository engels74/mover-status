"""
Test cases for the configuration schema system.

This module tests the configuration schema system that provides:
- Schema definition with required and optional fields
- Schema validation against configuration data
- Schema inheritance and composition
"""

import pytest

# This will be implemented
from mover_status.config.schema import (
    ConfigSchema,
    SchemaField,
    SchemaValidationError,
    FieldType,
)


class TestSchemaField:
    """Test cases for schema field definition."""

    def test_create_required_field(self) -> None:
        """Test creating a required field."""
        field = SchemaField(
            name="test_field",
            field_type=FieldType.STRING,
            required=True,
            description="A test field"
        )

        assert field.name == "test_field"
        assert field.field_type == FieldType.STRING
        assert field.required is True
        assert field.description == "A test field"
        assert field.default_value is None

    def test_create_optional_field_with_default(self) -> None:
        """Test creating an optional field with a default value."""
        field = SchemaField(
            name="optional_field",
            field_type=FieldType.INTEGER,
            required=False,
            default_value=42,
            description="An optional field"
        )

        assert field.name == "optional_field"
        assert field.field_type == FieldType.INTEGER
        assert field.required is False
        assert field.default_value == 42
        assert field.description == "An optional field"

    def test_create_list_field(self) -> None:
        """Test creating a list field with item type."""
        field = SchemaField(
            name="list_field",
            field_type=FieldType.LIST,
            required=True,
            item_type=FieldType.STRING,
            description="A list of strings"
        )

        assert field.name == "list_field"
        assert field.field_type == FieldType.LIST
        assert field.item_type == FieldType.STRING
        assert field.required is True

    def test_create_dict_field(self) -> None:
        """Test creating a dictionary field with value type."""
        field = SchemaField(
            name="dict_field",
            field_type=FieldType.DICT,
            required=True,
            value_type=FieldType.INTEGER,
            description="A dictionary with integer values"
        )

        assert field.name == "dict_field"
        assert field.field_type == FieldType.DICT
        assert field.value_type == FieldType.INTEGER
        assert field.required is True


class TestConfigSchema:
    """Test cases for configuration schema definition."""

    def test_create_empty_schema(self) -> None:
        """Test creating an empty schema."""
        schema = ConfigSchema(name="empty_schema")

        assert schema.name == "empty_schema"
        assert len(schema.fields) == 0
        assert schema.parent is None

    def test_create_schema_with_fields(self) -> None:
        """Test creating a schema with fields."""
        fields = [
            SchemaField("name", FieldType.STRING, required=True),
            SchemaField("age", FieldType.INTEGER, required=False, default_value=0),
        ]

        schema = ConfigSchema(name="person_schema", fields=fields)

        assert schema.name == "person_schema"
        assert len(schema.fields) == 2
        assert "name" in schema.fields
        assert "age" in schema.fields
        assert schema.fields["name"].required is True
        assert schema.fields["age"].required is False

    def test_add_field_to_schema(self) -> None:
        """Test adding a field to an existing schema."""
        schema = ConfigSchema(name="test_schema")
        field = SchemaField("test_field", FieldType.STRING, required=True)

        schema.add_field(field)

        assert len(schema.fields) == 1
        assert "test_field" in schema.fields
        assert schema.fields["test_field"] == field

    def test_schema_inheritance(self) -> None:
        """Test schema inheritance."""
        # Create parent schema
        parent_fields = [
            SchemaField("base_field", FieldType.STRING, required=True),
        ]
        parent_schema = ConfigSchema(name="parent_schema", fields=parent_fields)

        # Create child schema that inherits from parent
        child_fields = [
            SchemaField("child_field", FieldType.INTEGER, required=False),
        ]
        child_schema = ConfigSchema(
            name="child_schema",
            fields=child_fields,
            parent=parent_schema
        )

        assert child_schema.parent == parent_schema
        assert len(child_schema.get_all_fields()) == 2
        assert "base_field" in child_schema.get_all_fields()
        assert "child_field" in child_schema.get_all_fields()

    def test_schema_field_override(self) -> None:
        """Test that child schema can override parent fields."""
        # Create parent schema
        parent_fields = [
            SchemaField("shared_field", FieldType.STRING, required=True),
        ]
        parent_schema = ConfigSchema(name="parent_schema", fields=parent_fields)

        # Create child schema that overrides the shared field
        child_fields = [
            SchemaField("shared_field", FieldType.INTEGER, required=False),
        ]
        child_schema = ConfigSchema(
            name="child_schema",
            fields=child_fields,
            parent=parent_schema
        )

        all_fields = child_schema.get_all_fields()
        assert len(all_fields) == 1
        assert all_fields["shared_field"].field_type == FieldType.INTEGER
        assert all_fields["shared_field"].required is False


class TestSchemaValidation:
    """Test cases for schema validation."""

    def test_validate_valid_config(self) -> None:
        """Test validating a valid configuration."""
        fields = [
            SchemaField("name", FieldType.STRING, required=True),
            SchemaField("age", FieldType.INTEGER, required=False, default_value=0),
        ]
        schema = ConfigSchema(name="person_schema", fields=fields)

        config = {"name": "John", "age": 30}

        # Should not raise an exception
        result = schema.validate(config)
        assert result == config

    def test_validate_config_with_missing_required_field(self) -> None:
        """Test validation fails when required field is missing."""
        fields = [
            SchemaField("name", FieldType.STRING, required=True),
            SchemaField("age", FieldType.INTEGER, required=False),
        ]
        schema = ConfigSchema(name="person_schema", fields=fields)

        config = {"age": 30}  # Missing required 'name' field

        with pytest.raises(SchemaValidationError) as exc_info:
            _ = schema.validate(config)

        assert "name" in str(exc_info.value)
        assert "required" in str(exc_info.value).lower()

    def test_validate_config_with_wrong_type(self) -> None:
        """Test validation fails when field has wrong type."""
        fields = [
            SchemaField("name", FieldType.STRING, required=True),
            SchemaField("age", FieldType.INTEGER, required=True),
        ]
        schema = ConfigSchema(name="person_schema", fields=fields)

        config = {"name": "John", "age": "thirty"}  # age should be integer

        with pytest.raises(SchemaValidationError) as exc_info:
            _ = schema.validate(config)

        assert "age" in str(exc_info.value)
        assert "type" in str(exc_info.value).lower()

    def test_validate_config_with_defaults(self) -> None:
        """Test validation applies default values for missing optional fields."""
        fields = [
            SchemaField("name", FieldType.STRING, required=True),
            SchemaField("age", FieldType.INTEGER, required=False, default_value=25),
        ]
        schema = ConfigSchema(name="person_schema", fields=fields)

        config = {"name": "John"}  # Missing optional 'age' field

        result = schema.validate(config)
        assert result["name"] == "John"
        assert result["age"] == 25

    def test_validate_list_field(self) -> None:
        """Test validation of list fields."""
        fields = [
            SchemaField("tags", FieldType.LIST, required=True, item_type=FieldType.STRING),
        ]
        schema = ConfigSchema(name="tagged_schema", fields=fields)

        config = {"tags": ["tag1", "tag2", "tag3"]}

        result = schema.validate(config)
        assert result == config

    def test_validate_invalid_list_field(self) -> None:
        """Test validation fails for invalid list items."""
        fields = [
            SchemaField("numbers", FieldType.LIST, required=True, item_type=FieldType.INTEGER),
        ]
        schema = ConfigSchema(name="numbers_schema", fields=fields)

        config = {"numbers": [1, 2, "three"]}  # "three" should be integer

        with pytest.raises(SchemaValidationError) as exc_info:
            _ = schema.validate(config)

        assert "numbers" in str(exc_info.value)

    def test_validate_dict_field(self) -> None:
        """Test validation of dictionary fields."""
        fields = [
            SchemaField("scores", FieldType.DICT, required=True, value_type=FieldType.INTEGER),
        ]
        schema = ConfigSchema(name="scores_schema", fields=fields)

        config = {"scores": {"math": 95, "science": 87}}

        result = schema.validate(config)
        assert result == config

    def test_validate_invalid_dict_field(self) -> None:
        """Test validation fails for invalid dictionary values."""
        fields = [
            SchemaField("scores", FieldType.DICT, required=True, value_type=FieldType.INTEGER),
        ]
        schema = ConfigSchema(name="scores_schema", fields=fields)

        config = {"scores": {"math": 95, "science": "A+"}}  # "A+" should be integer

        with pytest.raises(SchemaValidationError) as exc_info:
            _ = schema.validate(config)

        assert "scores" in str(exc_info.value)


class TestSchemaComposition:
    """Test cases for schema composition."""

    def test_compose_schemas(self) -> None:
        """Test composing multiple schemas."""
        # Create first schema
        schema1_fields = [
            SchemaField("name", FieldType.STRING, required=True),
        ]
        schema1 = ConfigSchema(name="name_schema", fields=schema1_fields)

        # Create second schema
        schema2_fields = [
            SchemaField("age", FieldType.INTEGER, required=False, default_value=0),
        ]
        schema2 = ConfigSchema(name="age_schema", fields=schema2_fields)

        # Compose schemas
        composed_schema = ConfigSchema.compose(
            name="composed_schema",
            schemas=[schema1, schema2]
        )

        assert composed_schema.name == "composed_schema"
        all_fields = composed_schema.get_all_fields()
        assert len(all_fields) == 2
        assert "name" in all_fields
        assert "age" in all_fields

    def test_compose_schemas_with_conflicts(self) -> None:
        """Test composing schemas with field conflicts."""
        # Create first schema
        schema1_fields = [
            SchemaField("shared_field", FieldType.STRING, required=True),
        ]
        schema1 = ConfigSchema(name="schema1", fields=schema1_fields)

        # Create second schema with conflicting field
        schema2_fields = [
            SchemaField("shared_field", FieldType.INTEGER, required=False),
        ]
        schema2 = ConfigSchema(name="schema2", fields=schema2_fields)

        # Compose schemas - later schema should override
        composed_schema = ConfigSchema.compose(
            name="composed_schema",
            schemas=[schema1, schema2]
        )

        all_fields = composed_schema.get_all_fields()
        assert len(all_fields) == 1
        assert all_fields["shared_field"].field_type == FieldType.INTEGER
        assert all_fields["shared_field"].required is False
