"""
Calculation Utilities for the WHAT-TO-EAT-AGENT system.

This module implements calculation functions for the logistics and inventory system.
Based on DEV_SPEC.md Section 3.6.7 and 5.3.4
"""
from typing import Dict, List, Any
from decimal import Decimal


def calculate_shopping_gap(required_ingredients: List[Dict[str, Any]],
                          available_inventory: Dict[str, Any],
                          unit_converter=None) -> Dict[str, Any]:
    """
    Calculate the gap between required ingredients and available inventory.

    Implements the formula: Shopping_List = max(0, R - I)
    Where R = required ingredients, I = inventory

    Args:
        required_ingredients: List of required ingredients with amounts
        available_inventory: Current inventory
        unit_converter: Optional unit converter instance

    Returns:
        Dictionary containing the shopping list (gap between required and available)
    """
    shopping_list = {}

    for req_item in required_ingredients:
        item_name = req_item.get("item", "").lower()
        required_amount = req_item.get("amount", 0)
        required_unit = req_item.get("unit", "")

        # Check if item exists in inventory
        if item_name in available_inventory:
            inv_item = available_inventory[item_name]
            available_amount = inv_item.get("quantity", 0)
            available_unit = inv_item.get("unit", "")

            # If units are different, convert to comparable units if converter provided
            if required_unit != available_unit and required_unit and available_unit and unit_converter:
                try:
                    # Convert required amount to inventory unit
                    converted_required = unit_converter.convert(
                        required_amount, required_unit, available_unit
                    )
                    gap = max(0, converted_required - available_amount)

                    # Convert gap back to original required unit
                    gap = unit_converter.convert(gap, available_unit, required_unit)
                except Exception:
                    # If conversion fails, treat as incompatible and add full requirement
                    gap = required_amount
            else:
                # Same units, just subtract
                gap = max(0, required_amount - available_amount)

            # Add to shopping list if there's a gap
            if gap > 0:
                shopping_list[item_name] = {
                    "required": required_amount,
                    "available": available_amount,
                    "needed": gap,
                    "unit": required_unit
                }
        else:
            # Item not in inventory, add full requirement
            shopping_list[item_name] = {
                "required": required_amount,
                "available": 0,
                "needed": required_amount,
                "unit": required_unit
            }

    return shopping_list


def calculate_nutritional_values(ingredients: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate approximate nutritional values for a list of ingredients.

    Args:
        ingredients: List of ingredients with amounts

    Returns:
        Dictionary containing estimated nutritional values
    """
    # This is a simplified implementation
    # In a real system, this would access a nutritional database
    nutrition_totals = {
        "calories": 0,
        "protein_g": 0,
        "carbs_g": 0,
        "fat_g": 0
    }

    # Average nutritional values per 100g (simplified)
    avg_nutrition = {
        "vegetables": {"calories": 25, "protein_g": 1, "carbs_g": 5, "fat_g": 0.2},
        "fruits": {"calories": 60, "protein_g": 0.5, "carbs_g": 14, "fat_g": 0.2},
        "grains": {"calories": 350, "protein_g": 10, "carbs_g": 75, "fat_g": 3},
        "protein": {"calories": 130, "protein_g": 25, "carbs_g": 0, "fat_g": 3},
        "dairy": {"calories": 100, "protein_g": 8, "carbs_g": 12, "fat_g": 3},
    }

    for ingredient in ingredients:
        item_name = ingredient.get("item", "").lower()
        amount = ingredient.get("amount", 0)
        unit = ingredient.get("unit", "")

        # Convert amount to grams for calculation if needed
        multiplier = 1
        if unit == 'kg':
            multiplier = 1000
        elif unit == 'mg':
            multiplier = 0.001
        elif unit == 'oz':
            multiplier = 28.35
        elif unit == 'lb':
            multiplier = 453.592

        gram_amount = amount * multiplier

        # Estimate nutrition type based on common ingredients
        nutrition_type = "vegetables"  # default
        if any(protein_word in item_name for protein_word in ["chicken", "beef", "fish", "tofu", "egg", "meat", "pork"]):
            nutrition_type = "protein"
        elif any(grain_word in item_name for grain_word in ["rice", "pasta", "bread", "oats", "flour", "wheat"]):
            nutrition_type = "grains"
        elif any(dairy_word in item_name for dairy_word in ["milk", "cheese", "yogurt", "butter", "cream"]):
            nutrition_type = "dairy"
        elif any(veg_word in item_name for veg_word in ["carrot", "broccoli", "spinach", "lettuce", "pepper"]):
            nutrition_type = "vegetables"
        elif any(fruit_word in item_name for fruit_word in ["apple", "banana", "orange", "berry", "grape"]):
            nutrition_type = "fruits"

        # Add to totals based on ratio (per 100g)
        nutrition_data = avg_nutrition[nutrition_type]
        ratio = gram_amount / 100.0

        for nutrient, value in nutrition_data.items():
            nutrition_totals[nutrient] += value * ratio

    return nutrition_totals