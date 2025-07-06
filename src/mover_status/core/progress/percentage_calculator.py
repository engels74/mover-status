"""Progress percentage calculation implementation."""

from __future__ import annotations

from decimal import Decimal

# Type alias for numeric types using modern Python 3.13 syntax
Number = int | float | Decimal


class ProgressPercentageCalculator:
    """Calculator for progress percentages with configurable precision and validation."""
    
    precision: int
    
    def __init__(self, precision: int = 2) -> None:
        """Initialize the progress percentage calculator.
        
        Args:
            precision: Number of decimal places to round the result to (default: 2)
        """
        if precision < 0:
            raise ValueError("Precision must be a non-negative integer")
        
        self.precision = precision
    
    def calculate_percentage(self, progress: Number, total: Number) -> float:
        """Calculate the percentage of progress completed.
        
        Args:
            progress: The current progress value (bytes transferred, items processed, etc.)
            total: The total target value
            
        Returns:
            The percentage as a float value, capped at 100.0
            
        Raises:
            ValueError: If progress or total are negative, or if total is zero with non-zero progress
        """
        # Type validation - runtime checks for edge cases
        # Note: Type hints ensure compile-time type safety, but we still need runtime validation
        # for cases where the function might be called with invalid types at runtime
        
        # Convert to float for calculation
        progress_val = float(progress)
        total_val = float(total)
        
        # Value validation
        if progress_val < 0:
            raise ValueError("Progress cannot be negative")
        
        if total_val < 0:
            raise ValueError("Total cannot be negative")
        
        # Special case: zero total
        if total_val == 0:
            if progress_val == 0:
                # Zero progress of zero total is 100% complete
                return 100.0
            else:
                # Non-zero progress with zero total is invalid
                raise ValueError("Cannot calculate percentage with zero total")
        
        # Calculate percentage
        percentage = (progress_val / total_val) * 100.0
        
        # Determine effective precision
        effective_precision = self.precision
        
        # For Decimal inputs, use higher precision if both inputs are Decimal
        if isinstance(progress, Decimal) and isinstance(total, Decimal):
            # Calculate decimal precision of the result
            decimal_result = (Decimal(str(progress_val)) / Decimal(str(total_val))) * 100
            decimal_str = str(decimal_result)
            if '.' in decimal_str:
                decimal_places = len(decimal_str.split('.')[1].rstrip('0'))
                effective_precision = max(self.precision, min(decimal_places, 6))
        
        # Apply precision rounding first, then cap at 100%
        if effective_precision == 0:
            percentage = float(round(percentage))
        else:
            percentage = round(percentage, effective_precision)
        
        # Cap at 100% after precision rounding
        if percentage > 100.0:
            percentage = 100.0
            
        return percentage 