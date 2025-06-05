from src.main import build_graph  # Changed from 'main' to 'src.main'
from langsmith import Client
from typing import Dict
from langchain_core.messages import HumanMessage
from langgraph.graph import END

# Initialize client and graph
client = Client()
graph = build_graph()  # Initialize graph once

# Dataset name
dataset_name = "Chinook Customer Service Bot: E2E"

# Evaluator functions
def correct(outputs: dict, reference_outputs: dict) -> bool:
    """Check if the agent chose the correct route."""
    return outputs["route"] == reference_outputs["route"]

def final_answer_correct(outputs: dict, reference_outputs: dict) -> float:
    """Check if the final answer matches expected response pattern."""
    answer = outputs.get("response", "").lower()
    expected = reference_outputs.get("expected_response", "").lower()
    
    # Check for key phrases in responses
    if "music_query" in reference_outputs.get("route", ""):
        return any(phrase in answer for phrase in ["track", "album", "artist", "duration"])
    elif "refund" in reference_outputs.get("route", ""):
        return any(phrase in answer for phrase in ["refund", "invoice", "amount"])
    return False

# Function to run graph with input
async def run_graph(inputs: dict) -> dict:
    """Run graph and track the trajectory it takes along with the final response."""
    result = await graph.ainvoke(
        {
            "messages": [
                {"role": "user", "content": inputs["question"]},
            ]
        },
        config={"env": "test"},
    )
    return {"response": result["followup"]}

# Target function for running intent classifier
async def run_intent_classifier(inputs: dict) -> dict:
    """Run only the intent classifier node."""
    command = await graph.nodes["route"].ainvoke(inputs)
    return {"route": command.goto}

# Run evaluation function
async def run_evaluations():
    # Test intent classification
    intent_results = await client.aevaluate(
        run_intent_classifier,
        data=dataset_name,
        evaluators=[correct],
        experiment_prefix="music-store-intent-classifier",
        max_concurrency=4,
    )
    
    # Test end-to-end responses
    e2e_results = await client.aevaluate(
        run_graph,
        data=dataset_name,
        evaluators=[final_answer_correct],
        experiment_prefix="music-store-e2e",
        max_concurrency=4,
    )
    
    return intent_results, e2e_results

# Example test cases for the dataset
example_test_cases = [
    {
        "question": "Do you have any Pink Floyd albums?",
        "route": "music_query",
        "expected_response": "Here are the matching tracks"
    },
    {
        "question": "I want a refund for my purchase",
        "route": "gather_info",
        "expected_response": "To help you with a refund"
    },
    {
        "question": "Hi, what can you help me with?",
        "route": "default_response",
        "expected_response": "I'm your music store assistant"
    }
]

if __name__ == "__main__":
    import asyncio
    # Initialize graph
    graph = build_graph()
    # Run evaluations
    results = asyncio.run(run_evaluations())
    print(results[0].to_pandas())  # Intent classification results
    print(results[1].to_pandas())  # E2E results