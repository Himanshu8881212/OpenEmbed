#!/bin/bash

# ============================================================================
# EMBEd - Easy Start Script
# ============================================================================

set -e

echo "🚀 EMBEd - Multi-Modal Embedding Warehouse"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running!"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is installed and running"
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "⚠️  docker-compose not found, using 'docker compose' instead"
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Function to show menu
show_menu() {
    echo ""
    echo "What would you like to do?"
    echo "1) 🏗️  Build and start EMBEd (first time setup)"
    echo "2) ▶️  Start EMBEd"
    echo "3) ⏹️  Stop EMBEd"
    echo "4) 🔄 Restart EMBEd"
    echo "5) 📋 View logs"
    echo "6) 🔍 Check status"
    echo "7) 🧹 Clean up (remove all data)"
    echo "8) ❌ Exit"
    echo ""
    read -p "Enter your choice [1-8]: " choice
}

# Function to build and start
build_and_start() {
    echo ""
    echo "🏗️  Building Docker image (this may take 10-15 minutes on first run)..."
    $COMPOSE_CMD build
    
    echo ""
    echo "▶️  Starting EMBEd..."
    $COMPOSE_CMD up -d
    
    echo ""
    echo "⏳ Waiting for application to start (this may take 2-3 minutes on first run)..."
    sleep 5
    
    echo ""
    echo "📋 Checking logs..."
    $COMPOSE_CMD logs --tail=50
    
    echo ""
    echo "✅ EMBEd is starting!"
    echo ""
    echo "🌐 Access the application at:"
    echo "   Frontend:    http://localhost:8000"
    echo "   API Docs:    http://localhost:8000/docs"
    echo "   Health:      http://localhost:8000/api/health"
    echo ""
    echo "💡 Tip: Run './start.sh' and choose option 5 to view logs"
}

# Function to start
start() {
    echo ""
    echo "▶️  Starting EMBEd..."
    $COMPOSE_CMD up -d
    
    echo ""
    echo "✅ EMBEd started!"
    echo ""
    echo "🌐 Access at: http://localhost:8000"
}

# Function to stop
stop() {
    echo ""
    echo "⏹️  Stopping EMBEd..."
    $COMPOSE_CMD down
    
    echo ""
    echo "✅ EMBEd stopped!"
}

# Function to restart
restart() {
    echo ""
    echo "🔄 Restarting EMBEd..."
    $COMPOSE_CMD restart
    
    echo ""
    echo "✅ EMBEd restarted!"
}

# Function to view logs
view_logs() {
    echo ""
    echo "📋 Viewing logs (press Ctrl+C to exit)..."
    echo ""
    $COMPOSE_CMD logs -f
}

# Function to check status
check_status() {
    echo ""
    echo "🔍 Checking status..."
    echo ""
    $COMPOSE_CMD ps
    
    echo ""
    echo "📊 Resource usage:"
    docker stats --no-stream embed-app 2>/dev/null || echo "Container not running"
    
    echo ""
    echo "💾 Disk usage:"
    docker system df
}

# Function to clean up
clean_up() {
    echo ""
    echo "⚠️  WARNING: This will delete ALL data including:"
    echo "   - Vector database"
    echo "   - Uploaded files"
    echo "   - Analytics database"
    echo "   - Model cache"
    echo ""
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        echo ""
        echo "🧹 Cleaning up..."
        $COMPOSE_CMD down -v
        
        echo ""
        echo "✅ All data removed!"
    else
        echo ""
        echo "❌ Cancelled"
    fi
}

# Main loop
while true; do
    show_menu
    
    case $choice in
        1)
            build_and_start
            ;;
        2)
            start
            ;;
        3)
            stop
            ;;
        4)
            restart
            ;;
        5)
            view_logs
            ;;
        6)
            check_status
            ;;
        7)
            clean_up
            ;;
        8)
            echo ""
            echo "👋 Goodbye!"
            exit 0
            ;;
        *)
            echo ""
            echo "❌ Invalid choice. Please enter 1-8."
            ;;
    esac
done

