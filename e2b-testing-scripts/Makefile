.PHONY: help setup install clean test build switch-env list-envs show-env
.PHONY: test-all test-client test-host test-sandbox
.PHONY: report clean-outputs clean-reports
.DEFAULT_GOAL := help

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

# Config
PYTHON := python3
E2B := e2b
TEMPLATE_DIR := e2b-template
TESTS_DIR := tests
ENV_DIR := env
OUTPUTS_DIR := outputs
REPORTS_DIR := reports

help: ## Show this help message
	@echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "$(BLUE)  E2B Performance Testing - Makefile Commands$(NC)"
	@echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo ""
	@echo "Usage: make $(GREEN)<target>$(NC)"
	@echo ""
	@echo "$(BLUE)Setup & Installation:$(NC)"
	@echo "  $(GREEN)setup$(NC)              - Initialize project environment"
	@echo "  $(GREEN)install$(NC)            - Install Python dependencies"
	@echo "  $(GREEN)check-env$(NC)          - Check environment variables"
	@echo ""
	@echo "$(BLUE)Environment Management:$(NC)"
	@echo "  $(GREEN)list-envs$(NC)          - List all available environments"
	@echo "  $(GREEN)show-env$(NC)           - Show current environment info"
	@echo "  $(GREEN)switch-env ENV=name$(NC) - Switch to specified environment"
	@echo ""
	@echo "$(BLUE)E2B Template:$(NC)"
	@echo "  $(GREEN)build$(NC)              - Build E2B template"
	@echo "  $(GREEN)build-verbose$(NC)      - Build E2B template (verbose)"
	@echo "  $(GREEN)template-info$(NC)      - Show template information"
	@echo ""
	@echo "$(BLUE)Testing:$(NC)"
	@echo "  $(GREEN)test-all$(NC)           - Run all client tests"
	@echo "  $(GREEN)test-lifecycle$(NC)     - Run lifecycle tests"
	@echo "  $(GREEN)test-cold ITER=N$(NC)   - Run cold start tests (N times)"
	@echo "  $(GREEN)test-warm ITER=N$(NC)   - Run warm start tests (N times)"
	@echo "  $(GREEN)test-capacity$(NC)      - Run capacity tests"
	@echo "  $(GREEN)quick-test$(NC)         - Quick test (warm start 3x)"
	@echo "  $(GREEN)full-test$(NC)          - Full test suite"
	@echo ""
	@echo "$(BLUE)Reports & Cleanup:$(NC)"
	@echo "  $(GREEN)report$(NC)             - Show test report summary"
	@echo "  $(GREEN)clean$(NC)              - Clean temporary files"
	@echo "  $(GREEN)clean-outputs$(NC)      - Clean output files"
	@echo ""
	@echo "$(BLUE)Development:$(NC)"
	@echo "  $(GREEN)status$(NC)             - Show project status"
	@echo "  $(GREEN)validate$(NC)           - Validate project configuration"
	@echo ""

setup: ## Initialize project environment
	@echo "$(BLUE)Initializing project environment...$(NC)"
	@./setup.sh

install: ## Install Python dependencies
	@echo "$(BLUE)Installing Python dependencies...$(NC)"
	@if [ -f "$(TESTS_DIR)/requirements.txt" ]; then \
		pip3 install -r $(TESTS_DIR)/requirements.txt; \
	else \
		pip3 install e2b pyyaml boto3 azure-storage-blob azure-identity; \
	fi
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

check-env: ## Check environment variables
	@echo "$(BLUE)Checking environment variables...$(NC)"
	@if [ -f "$(ENV_DIR)/.e2b_env.template" ]; then \
		echo "$(GREEN)✓ Environment template found$(NC)"; \
	else \
		echo "$(YELLOW)⚠ Environment template not found$(NC)"; \
	fi
	@if [ -n "$$E2B_DOMAIN" ]; then \
		echo "$(GREEN)✓ Environment variables loaded$(NC)"; \
		echo "  E2B_DOMAIN: $$E2B_DOMAIN"; \
		echo "  CLOUD_PROVIDER: $${CLOUD_PROVIDER:-not set}"; \
	else \
		echo "$(YELLOW)⚠ Environment variables not loaded$(NC)"; \
		echo "  Run: source env/.e2b_env"; \
	fi

switch-env: ## Switch environment (use ENV=name)
	@if [ -z "$(ENV)" ]; then \
		echo "$(YELLOW)Usage: make switch-env ENV=awsdev$(NC)"; \
		./switch-env.sh --list; \
	else \
		./switch-env.sh $(ENV); \
	fi

list-envs: ## List all available environments
	@./switch-env.sh --list

show-env: ## Show current environment info
	@./switch-env.sh --current

build: ## Build E2B template (with timing)
	@echo "$(BLUE)Building E2B template...$(NC)"
	@mkdir -p $(OUTPUTS_DIR)
	@start_time=$$(date +%s.%N); \
	cd $(TEMPLATE_DIR) && $(E2B) template build; \
	build_status=$$?; \
	end_time=$$(date +%s.%N); \
	elapsed=$$(echo "$$end_time - $$start_time" | bc); \
	elapsed_int=$$(printf "%.2f" $$elapsed); \
	if [ $$build_status -eq 0 ]; then \
		echo "$(GREEN)✓ Template built in $$elapsed_int seconds$(NC)"; \
		echo "{\"build_time_seconds\": $$elapsed_int, \"status\": \"success\", \"timestamp\": \"$$(date -Iseconds)\"}" > ../$(OUTPUTS_DIR)/template_build_time.json; \
		echo "$(GREEN)✓ Build time saved to $(OUTPUTS_DIR)/template_build_time.json$(NC)"; \
	else \
		echo "$(YELLOW)✗ Template build failed after $$elapsed_int seconds$(NC)"; \
		echo "{\"build_time_seconds\": $$elapsed_int, \"status\": \"failed\", \"timestamp\": \"$$(date -Iseconds)\"}" > ../$(OUTPUTS_DIR)/template_build_time.json; \
		exit $$build_status; \
	fi

build-verbose: ## Build E2B template (verbose)
	@echo "$(BLUE)Building E2B template (verbose)...$(NC)"
	@cd $(TEMPLATE_DIR) && $(E2B) template build --verbose

template-info: ## Show current E2B template info
	@echo "$(BLUE)Current E2B template configuration:$(NC)"
	@if [ -f "$(TEMPLATE_DIR)/e2b.toml" ]; then \
		grep -E "^(template_name|template_id|memory_mb|cpu_count)" $(TEMPLATE_DIR)/e2b.toml | sed 's/^/  /'; \
	else \
		echo "$(YELLOW)⚠ e2b.toml not found$(NC)"; \
	fi

test-all: ## Run all client tests
	@echo "$(BLUE)Running all client tests...$(NC)"
	@$(PYTHON) $(TESTS_DIR)/client/run_all_tests.py

test-lifecycle: ## Run sandbox lifecycle tests
	@echo "$(BLUE)Running sandbox lifecycle tests...$(NC)"
	@$(PYTHON) $(TESTS_DIR)/client/01_sandbox_lifecycle.py --test all

test-cold: ## Run cold start tests (ITER=N, default 3)
	@echo "$(BLUE)Running cold start tests...$(NC)"
	@$(PYTHON) $(TESTS_DIR)/client/01_sandbox_lifecycle.py --test cold --iterations $(or $(ITER),3)

test-warm: ## Run warm start tests (ITER=N, default 10)
	@echo "$(BLUE)Running warm start tests...$(NC)"
	@$(PYTHON) $(TESTS_DIR)/client/01_sandbox_lifecycle.py --test warm --iterations $(or $(ITER),10)

test-capacity: ## Run capacity tests
	@echo "$(BLUE)Running capacity tests...$(NC)"
	# @$(PYTHON) $(TESTS_DIR)/client/06_sandbox_capacity.py \
	# 	--batch-size $(or $(BATCH),10) \
	# 	--max-sandboxes $(or $(MAX),200)
	python3 tests/client/06_sandbox_capacity.py --batch-size 10 --interval 10 --max-sandboxes 10  --maintain-lifecycle --max-lifetime 600

test-host: ## Run host performance tests
	@echo "$(BLUE)Running host performance tests...$(NC)"
	@$(PYTHON) $(TESTS_DIR)/host/04_host_performance.py --test all

quick-test: ## Quick test (warm start 3x)
	@echo "$(BLUE)Quick test (warm start 3 times)...$(NC)"
	@$(PYTHON) $(TESTS_DIR)/client/01_sandbox_lifecycle.py --test warm --iterations 3

full-test: check-env test-lifecycle ## Full test suite
	@echo "$(GREEN)✓ Full test completed$(NC)"
	@$(MAKE) --no-print-directory report

report: ## Show test report summary
	@echo "$(BLUE)Test Report Summary:$(NC)"
	@echo ""
	@if [ -d "$(REPORTS_DIR)" ] && [ -n "$$(ls -A $(REPORTS_DIR) 2>/dev/null)" ]; then \
		ls -lh $(REPORTS_DIR)/*.md 2>/dev/null | awk '{print "  " $$9 " (" $$5 ")"}'; \
	else \
		echo "  $(YELLOW)No reports found$(NC)"; \
	fi

clean-outputs: ## Clean temporary output files
	@echo "$(BLUE)Cleaning temporary output files...$(NC)"
	@rm -rf $(OUTPUTS_DIR)/*.json
	@rm -rf $(OUTPUTS_DIR)/sandbox_tests/
	@echo "$(GREEN)✓ Outputs cleaned$(NC)"

clean: clean-outputs ## Clean all generated files
	@echo "$(BLUE)Cleaning Python cache...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

validate: ## Validate project configuration
	@echo "$(BLUE)Validating project configuration...$(NC)"
	@echo ""
	@echo "$(BLUE)1. Directory structure:$(NC)"
	@for dir in $(TEMPLATE_DIR) $(ENV_DIR) $(TESTS_DIR) $(OUTPUTS_DIR) $(REPORTS_DIR); do \
		if [ -d "$$dir" ]; then \
			echo "  $(GREEN)✓$(NC) $$dir"; \
		else \
			echo "  $(YELLOW)✗$(NC) $$dir (missing)"; \
		fi \
	done
	@echo ""
	@echo "$(BLUE)2. Key files:$(NC)"
	@for file in $(TEMPLATE_DIR)/e2b.Dockerfile $(ENV_DIR)/.e2b_env.template switch-env.sh; do \
		if [ -f "$$file" ]; then \
			echo "  $(GREEN)✓$(NC) $$file"; \
		else \
			echo "  $(YELLOW)✗$(NC) $$file (missing)"; \
		fi \
	done
	@echo ""
	@$(MAKE) --no-print-directory check-env

status: ## Show project status
	@echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "$(BLUE)  E2B Performance Testing - Project Status$(NC)"
	@echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo ""
	@$(MAKE) --no-print-directory show-env
	@echo ""
	@$(MAKE) --no-print-directory template-info
	@echo ""
	@echo "$(BLUE)Available environments:$(NC)"
	@./switch-env.sh --list | tail -n +2
	@echo ""
	@echo "$(BLUE)Recent test reports:$(NC)"
	@ls -lt $(REPORTS_DIR)/*.md 2>/dev/null | head -3 | awk '{print "  " $$9}' || echo "  $(YELLOW)No reports$(NC)"
	@echo ""
