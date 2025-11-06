#!/bin/bash

echo "=== Testing EMBEd API ==="
echo

BASE_URL="http://localhost:8000/api"

# Test 1: Health Check
echo "1. Testing Health Check..."
curl -s ${BASE_URL}/health | jq '.'
echo

# Test 2: Create Vector Store
echo "2. Creating Vector Store..."
curl -s -X POST ${BASE_URL}/vector-stores \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_store",
    "description": "Test vector store"
  }' | jq '.'
echo

# Test 3: List Vector Stores
echo "3. Listing Vector Stores..."
curl -s ${BASE_URL}/vector-stores | jq '.'
echo

# Test 4: Get Specific Vector Store
echo "4. Getting Vector Store Info..."
curl -s ${BASE_URL}/vector-stores/test_store | jq '.'
echo

echo "=== API Tests Complete ==="
echo "Note: Upload and embedding tests require the models to be loaded."
echo "Access the web UI at: http://localhost:8000"
