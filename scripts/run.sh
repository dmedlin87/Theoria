#!/usr/bin/env bash
# Theoria Intelligent Runner (Bash version)
# Cross-platform script for Linux/macOS

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PATH="$PROJECT_ROOT/theo"
WEB_PATH="$PROJECT_ROOT/theo/services/web"
VENV_PATH="$PROJECT_ROOT/.venv"
ENV_FILE="$PROJECT_ROOT/.env"
WEB_ENV_FILE="$WEB_PATH/.env.local"

MODE="${1:-full}"
PORT="${THEO_API_PORT:-8000}"
WEB_PORT="${THEO_WEB_PORT:-3001}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

print_header() {
    echo -e "\n${MAGENTA}$(printf '=%.0s' {1..80})${NC}"
    echo -e "${MAGENTA}  $1${NC}"
    echo -e "${MAGENTA}$(printf '=%.0s' {1..80})${NC}\n"
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

port_in_use() {
    lsof -i :"$1" >/dev/null 2>&1 || netstat -an | grep -q ":$1 "
}

stop_port() {
    local port=$1
    if port_in_use "$port"; then
        print_step "Stopping existing service on port $port..."
        lsof -ti :"$port" | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

# ============================================================================
# SETUP FUNCTIONS
# ============================================================================

setup_python_env() {
    print_step "Setting up Python environment..."
    
    if [ ! -d "$VENV_PATH" ]; then
        print_step "Creating virtual environment..."
        python3 -m venv "$VENV_PATH"
        print_success "Virtual environment created"
    fi
    
    source "$VENV_PATH/bin/activate"
    
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        print_step "Installing Python dependencies..."
        pip install -q --upgrade pip
        pip install -q -r "$PROJECT_ROOT/requirements.txt"
        print_success "Python dependencies installed"
    fi
}

setup_node_env() {
    print_step "Setting up Node.js environment..."
    
    cd "$WEB_PATH"
    if [ ! -d "node_modules" ] || [ "package-lock.json" -nt "node_modules" ]; then
        print_step "Installing Node.js dependencies..."
        npm install --silent
        print_success "Node.js dependencies installed"
    else
        print_success "Node.js dependencies up to date"
    fi
    cd "$PROJECT_ROOT"
}

setup_env_files() {
    print_step "Checking environment configuration..."
    
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$PROJECT_ROOT/.env.example" ]; then
            cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
            print_success "Created .env from .env.example"
        else
            print_warn "Creating minimal .env file"
            cat > "$ENV_FILE" <<EOF
# Theoria Configuration
database_url=sqlite:///./theo.db
storage_root=./storage
redis_url=redis://localhost:6379/0
THEO_AUTH_ALLOW_ANONYMOUS=1
embedding_model=BAAI/bge-m3
embedding_dim=1024
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$PORT
API_BASE_URL=http://127.0.0.1:$PORT
EOF
            print_success "Created minimal .env file"
        fi
    fi
    
    if [ ! -f "$WEB_ENV_FILE" ]; then
        cat > "$WEB_ENV_FILE" <<EOF
# Theoria Web - Local Development
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$PORT
API_BASE_URL=http://127.0.0.1:$PORT
EOF
        print_success "Created web/.env.local"
    fi
}

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    local issues=()
    
    print_step "Checking Python..."
    if command_exists python3; then
        version=$(python3 --version)
        print_success "Python found: $version"
    else
        issues+=("Python 3.11+ not found")
        print_error "Python not found"
    fi
    
    print_step "Checking Node.js..."
    if command_exists node; then
        version=$(node --version)
        print_success "Node.js found: $version"
    else
        issues+=("Node.js not found")
        print_error "Node.js not found"
    fi
    
    print_step "Checking npm..."
    if command_exists npm; then
        version=$(npm --version)
        print_success "npm found: v$version"
    else
        issues+=("npm not found")
        print_error "npm not found"
    fi
    
    if [ ${#issues[@]} -gt 0 ]; then
        echo ""
        print_error "Prerequisites check failed:"
        for issue in "${issues[@]}"; do
            echo -e "  - $issue"
        done
        exit 1
    fi
    
    print_success "All prerequisites satisfied"
}

# ============================================================================
# SERVICE FUNCTIONS
# ============================================================================

start_api() {
    print_header "Starting API Service"
    
    stop_port "$PORT"
    
    setup_python_env
    
    print_step "Starting FastAPI server on port $PORT..."
    
    cd "$PROJECT_ROOT"
    source "$VENV_PATH/bin/activate"
    
    python -m uvicorn theo.services.api.app.bootstrap.app_factory:create_app --factory \
        --host 127.0.0.1 \
        --port "$PORT" \
        --reload &
    
    API_PID=$!
    
    print_step "Waiting for API to start..."
    for i in {1..30}; do
        if curl -s "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
            print_success "API service started successfully"
            echo -e "  ${CYAN}→ API:    http://127.0.0.1:$PORT${NC}"
            echo -e "  ${CYAN}→ Docs:   http://127.0.0.1:$PORT/docs${NC}"
            echo -e "  ${CYAN}→ Health: http://127.0.0.1:$PORT/health${NC}"
            return 0
        fi
        sleep 1
    done
    
    print_error "API failed to start within 30 seconds"
    kill $API_PID 2>/dev/null || true
    exit 1
}

start_web() {
    print_header "Starting Web Service"
    
    stop_port "$WEB_PORT"
    
    setup_node_env
    
    print_step "Starting Next.js server on port $WEB_PORT..."
    
    cd "$WEB_PATH"
    PORT=$WEB_PORT npm run dev &
    WEB_PID=$!
    
    print_step "Waiting for web service to start..."
    for i in {1..30}; do
        if curl -s "http://127.0.0.1:$WEB_PORT" >/dev/null 2>&1; then
            print_success "Web service started successfully"
            echo -e "  ${CYAN}→ Web:  http://127.0.0.1:$WEB_PORT${NC}"
            echo -e "  ${CYAN}→ Chat: http://127.0.0.1:$WEB_PORT/chat${NC}"
            return 0
        fi
        sleep 1
    done
    
    print_error "Web service failed to start within 30 seconds"
    kill $WEB_PID 2>/dev/null || true
    exit 1
}

cleanup() {
    echo ""
    print_step "Stopping services..."
    [ -n "${API_PID:-}" ] && kill $API_PID 2>/dev/null || true
    [ -n "${WEB_PID:-}" ] && kill $WEB_PID 2>/dev/null || true
    print_success "Services stopped"
    exit 0
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

show_banner() {
    cat <<'EOF'

████████╗██╗  ██╗███████╗ ██████╗     ███████╗███╗   ██╗ ██████╗ ██╗███╗   ██╗███████╗
╚══██╔══╝██║  ██║██╔════╝██╔═══██╗    ██╔════╝████╗  ██║██╔════╝ ██║████╗  ██║██╔════╝
   ██║   ███████║█████╗  ██║   ██║    █████╗  ██╔██╗ ██║██║  ███╗██║██╔██╗ ██║█████╗  
   ██║   ██╔══██║██╔══╝  ██║   ██║    ██╔══╝  ██║╚██╗██║██║   ██║██║██║╚██╗██║██╔══╝  
   ██║   ██║  ██║███████╗╚██████╔╝    ███████╗██║ ╚████║╚██████╔╝██║██║ ╚████║███████╗
   ╚═╝   ╚═╝  ╚═╝╚══════╝ ╚═════╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝╚══════╝

EOF
    echo -e "${CYAN}  Research Engine for Theological Corpora${NC}"
    echo -e "${YELLOW}  Mode: $MODE${NC}"
    echo ""
}

main() {
    show_banner
    
    trap cleanup SIGINT SIGTERM
    
    case "$MODE" in
        check)
            check_prerequisites
            print_success "Environment check complete"
            ;;
        
        api)
            check_prerequisites
            setup_env_files
            start_api
            echo ""
            print_success "API service is running"
            echo -e "  ${YELLOW}Press Ctrl+C to stop${NC}"
            echo ""
            wait $API_PID
            ;;
        
        web)
            check_prerequisites
            setup_env_files
            
            if ! port_in_use "$PORT"; then
                print_warn "API is not running on port $PORT"
                echo -e "  ${YELLOW}The web app requires the API to function properly.${NC}"
                echo -e "  ${YELLOW}Start the API first with: ./run.sh api${NC}"
                echo ""
            fi
            
            start_web
            echo ""
            print_success "Web service is running"
            echo -e "  ${YELLOW}Press Ctrl+C to stop${NC}"
            echo ""
            wait $WEB_PID
            ;;
        
        full|dev)
            check_prerequisites
            setup_env_files
            start_api
            sleep 2
            start_web
            
            echo ""
            print_header "Services Running"
            print_success "All services started successfully!"
            echo ""
            echo -e "  ${CYAN}API:  http://127.0.0.1:$PORT${NC}"
            echo -e "  ${CYAN}Web:  http://127.0.0.1:$WEB_PORT${NC}"
            echo -e "  ${CYAN}Docs: http://127.0.0.1:$PORT/docs${NC}"
            echo ""
            echo -e "  ${YELLOW}Press Ctrl+C to stop all services${NC}"
            echo ""
            
            wait
            ;;
        
        *)
            echo "Usage: $0 {full|api|web|dev|check}"
            echo ""
            echo "Modes:"
            echo "  full  - Start both API and Web services (default)"
            echo "  api   - Start only FastAPI backend"
            echo "  web   - Start only Next.js frontend"
            echo "  dev   - Development mode (same as full)"
            echo "  check - Validate environment and dependencies"
            exit 1
            ;;
    esac
}

main
