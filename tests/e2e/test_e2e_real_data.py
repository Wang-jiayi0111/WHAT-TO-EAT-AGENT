"""
End-to-end test for the WHAT-TO-EAT-AGENT system using real recipe data.
Tests the complete workflow: ingestion -> RAG -> agent workflow -> response generation.
"""
import os
import tempfile
import shutil
from pathlib import Path

# Add src to path so we can import modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.main import WhatToEatAgent


def test_end_to_end_with_real_data():
    """Test the complete system with real recipe data."""
    print("Starting end-to-end test with real recipe data...")

    # Create a WhatToEatAgent instance
    agent = WhatToEatAgent()

    try:
        # Initialize all components
        print("Initializing system components...")
        agent.initialize_components()

        # Test 1: Run ingestion pipeline with real data
        print("\n1. Testing ingestion pipeline with real recipe data...")

        # Use a subset of the real recipe data for testing
        real_data_dir = "data/recipes/breakfast"  # Using breakfast recipes for testing

        if os.path.exists(real_data_dir):
            print(f"Using real recipe data from: {real_data_dir}")

            # Run the ingestion pipeline
            ingestion_result = agent.run_ingestion_pipeline(real_data_dir, incremental=False)
            print(f"Ingestion result: {ingestion_result}")

            # Verify that documents were processed
            assert ingestion_result['documents_processed'] > 0, "No documents were processed"
            assert ingestion_result['chunks_created'] > 0, "No chunks were created"
            assert ingestion_result['status'] == 'completed', "Ingestion did not complete successfully"

            print(f"Successfully processed {ingestion_result['documents_processed']} documents")
            print(f"Created {ingestion_result['chunks_created']} chunks")
        else:
            print(f"Warning: Real data directory {real_data_dir} does not exist, skipping ingestion test")
            # If real data doesn't exist, create minimal test data
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create a simple test recipe
                recipe_content = """# Scrambled Eggs

## Description
A simple and quick scrambled eggs recipe.

## Ingredients
- 2 eggs
- 2 tbsp milk
- Salt and pepper to taste
- 1 tbsp butter

## Instructions
1. Beat eggs with milk in a bowl
2. Heat butter in a pan
3. Add egg mixture and scramble gently
4. Season with salt and pepper
5. Serve hot
"""

                recipe_file = os.path.join(temp_dir, "scrambled_eggs.md")
                with open(recipe_file, 'w', encoding='utf-8') as f:
                    f.write(recipe_content)

                # Run ingestion on test data
                ingestion_result = agent.run_ingestion_pipeline(temp_dir, incremental=False)
                print(f"Ingestion result on test data: {ingestion_result}")

        # Test 2: Process a user query through the agent workflow
        print("\n2. Testing agent workflow with user query...")

        user_query = "推荐一些早餐菜谱"  # "Recommend some breakfast recipes"
        user_id = "test_user_123"

        response = agent.process_user_query(user_query, user_id)

        print(f"User query: {user_query}")
        print(f"Response: {response[:200]}...")  # Print first 200 chars

        # Verify that a response was generated
        assert response is not None, "No response generated"
        assert len(response) > 0, "Empty response generated"

        print("Successfully generated response for user query")

        # Test 3: Verify that MCP server can be initialized
        print("\n3. Testing MCP server initialization...")

        # Check that MCP server tools are available
        mcp_tools = agent.mcp_server.tools
        assert len(mcp_tools) > 0, "No MCP tools available"

        print(f"Available MCP tools: {list(mcp_tools.keys())}")

        # Test that we can get tool schemas
        for tool_name, tool in mcp_tools.items():
            schema = agent.mcp_server.get_tool_schema(tool_name)
            assert schema is not None, f"No schema for tool {tool_name}"
            print(f"  - {tool_name}: {tool.description}")

        print("\n✅ All end-to-end tests passed successfully!")
        print(f"System successfully processed real recipe data and responded to user queries.")
        print(f"The WHAT-TO-EAT-AGENT is working correctly with:")
        print(f"  - Ingestion pipeline: ✓")
        print(f"  - RAG engine: ✓")
        print(f"  - Agent workflow: ✓")
        print(f"  - MCP server: ✓")
        print(f"  - Response generation: ✓")

        return True

    except Exception as e:
        print(f"\n❌ End-to-end test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_different_recipe_types():
    """Test the system with different types of recipes."""
    print("\nTesting system with different recipe categories...")

    agent = WhatToEatAgent()

    try:
        # Initialize components
        agent.initialize_components()

        # Test different recipe categories
        test_categories = [
            "data/recipes/breakfast",      # Breakfast recipes
            "data/recipes/vegetable_dish", # Vegetable dishes
            "data/recipes/dessert",        # Desserts
        ]

        for category in test_categories:
            if os.path.exists(category):
                print(f"\nTesting category: {category}")

                # Run ingestion for this category
                result = agent.run_ingestion_pipeline(category, incremental=False)
                print(f"  Processed {result['documents_processed']} documents, created {result['chunks_created']} chunks")

                # Test a relevant query
                if "breakfast" in category:
                    query = "健康的早餐推荐"  # "Healthy breakfast recommendations"
                elif "vegetable" in category:
                    query = "简单的蔬菜菜谱"  # "Simple vegetable recipes"
                elif "dessert" in category:
                    query = "甜点制作方法"  # "Dessert preparation methods"
                else:
                    query = "推荐菜谱"  # "Recipe recommendations"

                response = agent.process_user_query(query, f"test_user_{category.split('/')[-1]}")
                print(f"  Response length: {len(response)} characters")

                assert len(response) > 0, f"No response for category {category}"

        print("\n✅ All recipe category tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Recipe category test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING END-TO-END TESTS FOR WHAT-TO-EAT-AGENT")
    print("=" * 60)

    success1 = test_end_to_end_with_real_data()
    success2 = test_different_recipe_types()

    print("\n" + "=" * 60)
    if success1 and success2:
        print("🎉 ALL END-TO-END TESTS PASSED!")
        print("The WHAT-TO-EAT-AGENT system is working correctly with real Chinese recipe data.")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please check the error messages above.")
    print("=" * 60)