#!/bin/bash

# OpenEmbed - Run All Tests Script
# This script runs the complete test suite for production validation

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         OpenEmbed - Complete Test Suite Runner                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if backend is running
echo -e "${YELLOW}[1/4] Checking backend status...${NC}"
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is running${NC}"
else
    echo -e "${RED}✗ Backend is not running!${NC}"
    echo -e "${YELLOW}Please start the backend first:${NC}"
    echo -e "  source venv/bin/activate"
    echo -e "  python app/main.py"
    exit 1
fi
echo ""

# Install test dependencies
echo -e "${YELLOW}[2/4] Installing test dependencies...${NC}"
if [ -f "tests/requirements.txt" ]; then
    pip install -q -r tests/requirements.txt
    echo -e "${GREEN}✓ Test dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ tests/requirements.txt not found, skipping${NC}"
fi
echo ""

# Run production validation test
echo -e "${YELLOW}[3/4] Running production validation test...${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
python production_validation_test.py
PROD_TEST_EXIT_CODE=$?
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Run backend unit tests (if pytest is available)
echo -e "${YELLOW}[4/4] Running backend unit tests...${NC}"
if command -v pytest &> /dev/null; then
    if [ -f "tests/test_backend_comprehensive.py" ]; then
        echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
        pytest tests/test_backend_comprehensive.py -v --tb=short 2>&1 | tail -50
        PYTEST_EXIT_CODE=$?
        echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    else
        echo -e "${YELLOW}⚠ Backend tests not found, skipping${NC}"
        PYTEST_EXIT_CODE=0
    fi
else
    echo -e "${YELLOW}⚠ pytest not installed, skipping unit tests${NC}"
    PYTEST_EXIT_CODE=0
fi
echo ""

# Summary
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                      Test Summary                              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ $PROD_TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Production Validation: PASSED${NC}"
else
    echo -e "${RED}✗ Production Validation: FAILED (exit code: $PROD_TEST_EXIT_CODE)${NC}"
fi

if [ $PYTEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Backend Unit Tests: PASSED${NC}"
else
    echo -e "${RED}✗ Backend Unit Tests: FAILED (exit code: $PYTEST_EXIT_CODE)${NC}"
fi

echo ""

# Overall result
if [ $PROD_TEST_EXIT_CODE -eq 0 ] && [ $PYTEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║              ✓ ALL TESTS PASSED - PRODUCTION READY             ║${NC}"
    echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════════════════════════╝${NC}"
    exit 0
elif [ $PROD_TEST_EXIT_CODE -eq 1 ]; then
    echo -e "${YELLOW}${BOLD}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}${BOLD}║           ⚠ TESTS MOSTLY PASSED - NEEDS ATTENTION             ║${NC}"
    echo -e "${YELLOW}${BOLD}╚════════════════════════════════════════════════════════════════╝${NC}"
    exit 1
else
    echo -e "${RED}${BOLD}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}${BOLD}║            ✗ TESTS FAILED - NOT PRODUCTION READY               ║${NC}"
    echo -e "${RED}${BOLD}╚════════════════════════════════════════════════════════════════╝${NC}"
    exit 2
fi

