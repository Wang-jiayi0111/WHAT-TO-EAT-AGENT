# Unit Conversion Center Utility

class UnitConverter:
    """Utility class for unit conversion."""

    UNIT_MAP = {
        "kg": 1000,  # kilograms to grams
        "g": 1,      # grams
        "mg": 0.001, # milligrams to grams
        "lb": 453.592, # pounds to grams
        "oz": 28.3495, # ounces to grams
    }

    def __init__(self):
        """
        Initialize the Unit Converter with predefined conversion rates.
        """
        self.conversion_rates = {
            # Example conversion rates
            ('kg', 'g'): 1000,
            ('g', 'kg'): 0.001,
            ('l', 'ml'): 1000,
            ('ml', 'l'): 0.001,
            ('cup', 'ml'): 240,
            ('tbsp', 'ml'): 15,
            ('tsp', 'ml'): 5,
        }

    @staticmethod
    def normalize(value: float, unit: str) -> float:
        """Normalize a value to grams.

        Args:
            value (float): The numeric value.
            unit (str): The unit of the value (e.g., 'kg', 'g', 'mg').

        Returns:
            float: The value converted to grams.

        Raises:
            ValueError: If the unit is not supported.
        """
        if unit not in UnitConverter.UNIT_MAP:
            raise ValueError(f"Unsupported unit: {unit}")
        return value * UnitConverter.UNIT_MAP[unit]

    @staticmethod
    def convert(value: float, from_unit: str, to_unit: str) -> float:
        """Convert a value from one unit to another.

        Args:
            value (float): The numeric value.
            from_unit (str): The original unit.
            to_unit (str): The target unit.

        Returns:
            float: The value converted to the target unit.

        Raises:
            ValueError: If either unit is not supported.
        """
        grams = UnitConverter.normalize(value, from_unit)
        if to_unit not in UnitConverter.UNIT_MAP:
            raise ValueError(f"Unsupported unit: {to_unit}")
        return grams / UnitConverter.UNIT_MAP[to_unit]

    def add_conversion_rate(self, from_unit, to_unit, rate):
        """
        Add a new conversion rate to the converter.

        :param from_unit: The unit to convert from.
        :param to_unit: The unit to convert to.
        :param rate: The conversion rate.
        """
        self.conversion_rates[(from_unit, to_unit)] = rate