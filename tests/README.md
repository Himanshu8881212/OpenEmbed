# OpenEmbed Test Suite

Comprehensive testing suite for the OpenEmbed multi-modal embedding warehouse.

## Test Structure

```
tests/
├── README.md                          # This file
├── test_backend_comprehensive.py     # Backend unit tests (pytest)
├── conftest.py                        # Pytest configuration
└── requirements.txt                   # Test dependencies

frontend/src/tests/
└── App.test.tsx                       # Frontend tests (Jest/React Testing Library)

production_validation_test.py          # End-to-end production validation
```

## Backend Tests

### Prerequisites

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Ensure backend is running
cd /path/to/EMBEd
source venv/bin/activate
python app/main.py
```

### Running Backend Unit Tests

```bash
# Run all backend tests
pytest tests/test_backend_comprehensive.py -v

# Run specific test class
pytest tests/test_backend_comprehensive.py::TestAPIHealth -v

# Run with coverage
pytest tests/test_backend_comprehensive.py --cov=app --cov-report=html

# Run in parallel (faster)
pytest tests/test_backend_comprehensive.py -n auto
```

### Test Categories

1. **TestAPIHealth** - API health and initialization
2. **TestFileUpload** - File upload for all modalities
3. **TestVectorStores** - Vector store CRUD operations
4. **TestEmbeddings** - Embedding generation and storage
5. **TestSearch** - Search functionality
6. **TestFileServing** - File serving endpoint
7. **TestEdgeCases** - Edge cases and error handling

## Frontend Tests

### Prerequisites

```bash
cd frontend
npm install
```

### Running Frontend Tests

```bash
# Run all frontend tests
npm test

# Run with coverage
npm test -- --coverage

# Run in watch mode
npm test -- --watch

# Run specific test file
npm test -- App.test.tsx
```

### Test Categories

1. **App Component** - Navigation and routing
2. **HomePage** - Dashboard metrics and display
3. **UploadPage** - File upload UI and interactions
4. **SearchPage** - Search UI and results
5. **VectorStoresPage** - Store management UI

## Production Validation Test

Comprehensive end-to-end test suite that validates production readiness.

### Running Production Validation

```bash
# Ensure backend is running on http://localhost:8000
source venv/bin/activate
python production_validation_test.py
```

### Test Coverage

1. ✅ API Health Check
2. ✅ Individual Modality Upload (7 modalities)
3. ✅ Multi-Modal Upload
4. ✅ Vector Store Creation
5. ✅ Add Embeddings to Stores
6. ✅ List All Vector Stores
7. ✅ Semantic Search & Retrieval
8. ✅ Cross-Modal Search
9. ✅ File Serving Endpoint

### Success Criteria

- **95%+ pass rate**: Production Ready ✓
- **80-94% pass rate**: Needs Attention ⚠
- **<80% pass rate**: Not Ready for Production ✗

## Test Files Required

The following test files must exist in `test_files/` directory:

```
test_files/
├── sample_text.txt
├── sample_image.jpg
├── sample_video.mp4
├── sample_audio.wav
├── sample_depth.png
├── sample_thermal.png
├── sample_imu.csv
└── test_sunset_ocean.txt
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r tests/requirements.txt
      - name: Run backend tests
        run: pytest tests/ -v --cov=app

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Node.js
        uses: actions/setup-node@v2
        with:
          node-version: 18
      - name: Install dependencies
        run: cd frontend && npm install
      - name: Run frontend tests
        run: cd frontend && npm test -- --coverage

  production-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Start backend
        run: |
          pip install -r requirements.txt
          python app/main.py &
          sleep 10
      - name: Run production validation
        run: python production_validation_test.py
```

## Test Best Practices

### Backend Tests

1. **Isolation**: Each test should be independent
2. **Cleanup**: Use fixtures to clean up test data
3. **Mocking**: Mock external dependencies when appropriate
4. **Assertions**: Use clear, specific assertions
5. **Coverage**: Aim for >80% code coverage

### Frontend Tests

1. **User-Centric**: Test from user's perspective
2. **Accessibility**: Test with screen readers in mind
3. **Async Handling**: Properly wait for async operations
4. **Mock API**: Mock API calls to avoid backend dependency
5. **Snapshots**: Use snapshot testing for UI consistency

## Troubleshooting

### Backend Tests Failing

```bash
# Check if backend is running
curl http://localhost:8000/api/health

# Clean ChromaDB
python -c "import shutil, os; path = './chroma_db'; shutil.rmtree(path) if os.path.exists(path) else None"

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Frontend Tests Failing

```bash
# Clear cache
cd frontend
rm -rf node_modules package-lock.json
npm install

# Update snapshots
npm test -- -u
```

### Production Validation Failing

```bash
# Ensure test files exist
ls -la test_files/

# Clean up vector stores
python -c "import shutil, os; path = './chroma_db'; shutil.rmtree(path) if os.path.exists(path) else None"

# Restart backend
pkill -f "python app/main.py"
python app/main.py
```

## Performance Benchmarks

Expected test execution times:

- Backend unit tests: ~30-60 seconds
- Frontend tests: ~10-20 seconds
- Production validation: ~2-5 minutes

## Contributing

When adding new features:

1. Write tests FIRST (TDD approach)
2. Ensure all existing tests pass
3. Add new tests for new functionality
4. Update this README if needed
5. Run full test suite before committing

## License

Same as OpenEmbed project license.

