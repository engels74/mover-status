"""
Configuration schema system for the Mover Status Monitor.

This module provides a flexible schema system for defining and validating
configuration structures. It supports:
- Field type validation
- Required and optional fields with defaults
- Schema inheritance and composition
- List and dictionary field validation
"""

from enum import Enum
from typing import TypeVar, final
from collections.abc import Mapping

# Type alias for configuration values - using object for maximum flexibility
# while maintaining type safety through runtime validation
ConfigValue = object
T = TypeVar("T")


class FieldType(Enum):
    """Enumeration of supported field types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"


@final
class SchemaValidationError(Exception):
    """
    Exception raised when schema validation fails.

    This exception includes information about the validation errors,
    such as missing required fields, incorrect field types, or invalid values.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        """
        Initialize the SchemaValidationError.

        Args:
            message: The error message.
            errors: Optional list of specific validation errors.
        """
        self.errors: list[str] = errors or []
        error_details = "\n - " + "\n - ".join(self.errors) if self.errors else ""
        super().__init__(f"{message}{error_details}")


@final
class SchemaField:
    """
    Represents a field in a configuration schema.

    A field defines the name, type, requirements, and validation rules
    for a configuration value.
    """

    def __init__(
        self,
        name: str,
        field_type: FieldType,
        required: bool = True,
        default_value: ConfigValue = None,
        description: str = "",
        item_type: FieldType | None = None,
        value_type: FieldType | None = None,
    ) -> None:
        """
        Initialize a schema field.

        Args:
            name: The field name.
            field_type: The expected type of the field value.
            required: Whether the field is required.
            default_value: Default value if the field is not provided.
            description: Human-readable description of the field.
            item_type: For LIST fields, the type of list items.
            value_type: For DICT fields, the type of dictionary values.
        """
        self.name = name
        self.field_type = field_type
        self.required = required
        self.default_value = default_value
        self.description = description
        self.item_type = item_type
        self.value_type = value_type

    def validate_value(self, value: ConfigValue) -> ConfigValue:
        """
        Validate a value against this field's requirements.

        Args:
            value: The value to validate.

        Returns:
            The validated value (may be converted to the correct type).

        Raises:
            SchemaValidationError: If the value is invalid.
        """
        if value is None:
            if self.required:
                raise SchemaValidationError(f"Field '{self.name}' is required")
            return self.default_value

        # Validate the field type
        if not self._is_valid_type(value, self.field_type):
            expected_type = self.field_type.value
            actual_type = type(value).__name__
            raise SchemaValidationError(
                f"Field '{self.name}' expected type {expected_type}, got {actual_type}"
            )

        # Additional validation for list and dict types
        if self.field_type == FieldType.LIST and self.item_type and isinstance(value, list):
            # Type narrowing: we know value is a list here
            self._validate_list_items(value)  # pyright: ignore[reportUnknownArgumentType]
        elif self.field_type == FieldType.DICT and self.value_type and isinstance(value, dict):
            # Type narrowing: we know value is a dict here
            self._validate_dict_values(value)  # pyright: ignore[reportUnknownArgumentType]

        return value  # pyright: ignore[reportUnknownVariableType]

    def _is_valid_type(self, value: ConfigValue, field_type: FieldType) -> bool:
        """Check if a value matches the expected field type."""
        type_mapping = {
            FieldType.STRING: str,
            FieldType.INTEGER: int,
            FieldType.FLOAT: (int, float),  # Allow int for float fields
            FieldType.BOOLEAN: bool,
            FieldType.LIST: list,
            FieldType.DICT: dict,
        }

        expected_types = type_mapping[field_type]
        return isinstance(value, expected_types)

    def _validate_list_items(self, value: list[object]) -> None:
        """Validate items in a list field."""
        if not self.item_type:
            return

        for i, item in enumerate(value):
            if not self._is_valid_type(item, self.item_type):
                expected_type = self.item_type.value
                actual_type = type(item).__name__
                raise SchemaValidationError(
                    f"Field '{self.name}' item {i} expected type {expected_type}, got {actual_type}"
                )

    def _validate_dict_values(self, value: dict[str, object]) -> None:
        """Validate values in a dictionary field."""
        if not self.value_type:
            return

        for key, dict_value in value.items():
            if not self._is_valid_type(dict_value, self.value_type):
                expected_type = self.value_type.value
                actual_type = type(dict_value).__name__
                raise SchemaValidationError(
                    f"Field '{self.name}' key '{key}' expected type {expected_type}, got {actual_type}"
                )


@final
class ConfigSchema:
    """
    Represents a configuration schema with fields and validation rules.

    A schema defines the structure and validation rules for a configuration
    section. It supports inheritance and composition for building complex
    configuration structures.
    """

    def __init__(
        self,
        name: str,
        fields: list[SchemaField] | None = None,
        parent: "ConfigSchema | None" = None,
    ) -> None:
        """
        Initialize a configuration schema.

        Args:
            name: The schema name.
            fields: List of fields in this schema.
            parent: Optional parent schema for inheritance.
        """
        self.name = name
        self.fields: dict[str, SchemaField] = {}
        self.parent = parent

        # Add fields to the schema
        if fields:
            for field in fields:
                self.add_field(field)

    def add_field(self, field: SchemaField) -> None:
        """
        Add a field to the schema.

        Args:
            field: The field to add.
        """
        self.fields[field.name] = field

    def get_all_fields(self) -> dict[str, SchemaField]:
        """
        Get all fields including inherited fields.

        Returns:
            Dictionary of all fields, with child fields overriding parent fields.
        """
        all_fields: dict[str, SchemaField] = {}

        # Start with parent fields if we have a parent
        if self.parent:
            all_fields.update(self.parent.get_all_fields())

        # Add our own fields (overriding parent fields with same name)
        all_fields.update(self.fields)

        return all_fields

    def validate(self, config: Mapping[str, ConfigValue]) -> dict[str, ConfigValue]:
        """
        Validate a configuration against this schema.

        Args:
            config: The configuration to validate.

        Returns:
            The validated configuration with defaults applied.

        Raises:
            SchemaValidationError: If the configuration is invalid.
        """
        errors: list[str] = []
        validated_config: dict[str, ConfigValue] = {}
        all_fields = self.get_all_fields()

        # Validate each field
        for field_name, field in all_fields.items():
            try:
                value = config.get(field_name)
                validated_value = field.validate_value(value)
                if validated_value is not None:
                    validated_config[field_name] = validated_value
            except SchemaValidationError as e:
                errors.extend(e.errors if e.errors else [str(e)])

        # Check for unknown fields
        for config_key in config:
            if config_key not in all_fields:
                errors.append(f"Unknown field '{config_key}' in schema '{self.name}'")

        # If there are validation errors, raise an exception
        if errors:
            raise SchemaValidationError(f"Schema validation failed for '{self.name}':", errors)

        return validated_config

    @classmethod
    def compose(cls, name: str, schemas: list["ConfigSchema"]) -> "ConfigSchema":
        """
        Compose multiple schemas into a single schema.

        Args:
            name: Name for the composed schema.
            schemas: List of schemas to compose.

        Returns:
            A new schema containing all fields from the input schemas.
            Later schemas override fields from earlier schemas.
        """
        composed_schema = cls(name=name)

        # Add fields from all schemas in order
        for schema in schemas:
            for field in schema.fields.values():
                composed_schema.add_field(field)

        return composed_schema
