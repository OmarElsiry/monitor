#!/bin/bash
# 🚀 Production Deployment Script for Nova TON Monitor

set -e  # Exit on any error

# Configuration
PROJECT_NAME="nova-ton-monitor"
DOCKER_COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env.production"
BACKUP_DIR="./backups"
LOG_FILE="./logs/deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

# Pre-deployment checks
pre_deployment_checks() {
    log "Running pre-deployment checks..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
    fi
    
    # Check if environment file exists
    if [ ! -f "$ENV_FILE" ]; then
        error "Environment file $ENV_FILE not found. Please create it from .env.production.template"
    fi
    
    # Check if required environment variables are set
    source "$ENV_FILE"
    if [ -z "$DB_PASSWORD" ] || [ -z "$TON_API_KEY" ]; then
        error "Required environment variables (DB_PASSWORD, TON_API_KEY) are not set in $ENV_FILE"
    fi
    
    success "Pre-deployment checks passed"
}

# Create necessary directories
create_directories() {
    log "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p data
    mkdir -p "$BACKUP_DIR"
    mkdir -p monitoring/grafana/dashboards
    mkdir -p monitoring/grafana/datasources
    mkdir -p nginx/ssl
    
    success "Directories created"
}

# Backup existing deployment
backup_existing() {
    if [ -d "data" ] && [ "$(ls -A data)" ]; then
        log "Backing up existing data..."
        
        BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR/$BACKUP_NAME"
        
        # Backup database
        if docker ps | grep -q nova-postgres; then
            log "Creating database backup..."
            docker exec nova-postgres pg_dump -U nova_user nova_ton_monitor > "$BACKUP_DIR/$BACKUP_NAME/database.sql"
        fi
        
        # Backup data directory
        cp -r data "$BACKUP_DIR/$BACKUP_NAME/"
        
        success "Backup created: $BACKUP_DIR/$BACKUP_NAME"
    fi
}

# Pull latest images
pull_images() {
    log "Pulling latest Docker images..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" pull
    success "Images pulled successfully"
}

# Build application image
build_application() {
    log "Building Nova TON Monitor image..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" build nova-monitor
    success "Application image built successfully"
}

# Deploy services
deploy_services() {
    log "Deploying services..."
    
    # Stop existing services
    docker-compose -f "$DOCKER_COMPOSE_FILE" down
    
    # Start services
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    
    success "Services deployed successfully"
}

# Wait for services to be healthy
wait_for_health() {
    log "Waiting for services to be healthy..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f "$DOCKER_COMPOSE_FILE" ps | grep -q "Up (healthy)"; then
            success "Services are healthy"
            return 0
        fi
        
        log "Attempt $attempt/$max_attempts - waiting for services to be healthy..."
        sleep 10
        ((attempt++))
    done
    
    error "Services failed to become healthy within timeout"
}

# Run post-deployment tests
post_deployment_tests() {
    log "Running post-deployment tests..."
    
    # Test API health endpoint
    if curl -f http://localhost:5001/api/health > /dev/null 2>&1; then
        success "API health check passed"
    else
        error "API health check failed"
    fi
    
    # Test database connectivity
    if docker exec nova-postgres pg_isready -U nova_user -d nova_ton_monitor > /dev/null 2>&1; then
        success "Database connectivity test passed"
    else
        error "Database connectivity test failed"
    fi
    
    success "Post-deployment tests passed"
}

# Show deployment status
show_status() {
    log "Deployment Status:"
    echo
    docker-compose -f "$DOCKER_COMPOSE_FILE" ps
    echo
    log "Service URLs:"
    echo "  API Server: http://localhost:5001"
    echo "  Health Check: http://localhost:5001/api/health"
    echo "  Metrics: http://localhost:9090"
    echo "  Grafana: http://localhost:3000"
    echo "  Prometheus: http://localhost:9091"
    echo
}

# Main deployment function
main() {
    log "Starting Nova TON Monitor deployment..."
    
    pre_deployment_checks
    create_directories
    backup_existing
    pull_images
    build_application
    deploy_services
    wait_for_health
    post_deployment_tests
    show_status
    
    success "Deployment completed successfully!"
    log "Check logs with: docker-compose logs -f nova-monitor"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "stop")
        log "Stopping services..."
        docker-compose -f "$DOCKER_COMPOSE_FILE" down
        success "Services stopped"
        ;;
    "restart")
        log "Restarting services..."
        docker-compose -f "$DOCKER_COMPOSE_FILE" restart
        success "Services restarted"
        ;;
    "logs")
        docker-compose -f "$DOCKER_COMPOSE_FILE" logs -f "${2:-nova-monitor}"
        ;;
    "status")
        show_status
        ;;
    "backup")
        backup_existing
        ;;
    *)
        echo "Usage: $0 {deploy|stop|restart|logs|status|backup}"
        echo "  deploy  - Full deployment (default)"
        echo "  stop    - Stop all services"
        echo "  restart - Restart all services"
        echo "  logs    - Show logs (optionally specify service name)"
        echo "  status  - Show deployment status"
        echo "  backup  - Create backup of current deployment"
        exit 1
        ;;
esac
