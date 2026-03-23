import unittest
from agent.nodes.logistics_node import LogisticsNode

class MockInventoryDB:
    def __init__(self, inventory):
        self.inventory = inventory

    def get_quantity(self, ingredient):
        return self.inventory.get(ingredient, 0)

class TestLogisticsNode(unittest.TestCase):

    def setUp(self):
        inventory = {
            'flour': 1000,  # grams
            'sugar': 500,   # grams
            'milk': 2       # liters
        }
        self.mock_inventory_db = MockInventoryDB(inventory)
        self.logistics_node = LogisticsNode(self.mock_inventory_db, None)  # Unit converter not needed for this test

    def test_fetch_inventory_snapshot(self):
        recipe_requirements = {
            'flour': 500,
            'sugar': 200,
            'milk': 1
        }
        snapshot = self.logistics_node.fetch_inventory_snapshot(recipe_requirements)
        self.assertEqual(snapshot, {
            'flour': 1000,
            'sugar': 500,
            'milk': 2
        })

    def test_calculate_shopping_list(self):
        recipe_requirements = {
            'flour': 1500,  # Need 1500g, have 1000g
            'sugar': 200,   # Need 200g, have 500g
            'milk': 3       # Need 3L, have 2L
        }
        inventory_snapshot = {
            'flour': 1000,
            'sugar': 500,
            'milk': 2
        }
        shopping_list = self.logistics_node.calculate_shopping_list(recipe_requirements, inventory_snapshot)
        self.assertEqual(shopping_list, {
            'flour': 500,  # Shortage of 500g
            'milk': 1      # Shortage of 1L
        })

    def test_update_shopping_list(self):
        shopping_list = {
            'flour': 500,
            'milk': 1
        }
        user_modifications = {
            'flour': -100,  # Reduce by 100g
            'sugar': 300    # Add 300g
        }
        updated_list = self.logistics_node.update_shopping_list(shopping_list, user_modifications)
        self.assertEqual(updated_list, {
            'flour': 400,  # 500 - 100
            'milk': 1,
            'sugar': 300   # New addition
        })

if __name__ == '__main__':
    unittest.main()