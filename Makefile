# ft_irc Test Runner Makefile
# Simple and easy to use

# Colors for beautiful output
GREEN = \033[0;32m
YELLOW = \033[0;33m
RED = \033[0;31m
BLUE = \033[0;34m
CYAN = \033[0;36m
BOLD = \033[1m
NC = \033[0m # No Color

# Default target - run the interactive test runner
.PHONY: all
all: test

# Main test runner (interactive mode)
.PHONY: test
test:
	@echo "$(CYAN)$(BOLD)🚀 Starting ft_irc Test Runner...$(NC)"
	@python3 irc_test_runner.py

# Quick test with auto-detection
.PHONY: quick
quick:
	@echo "$(CYAN)⚡ Quick test with auto-detection...$(NC)"
	@python3 irc_test_runner.py --binary ./ircserv 2>/dev/null || \
	python3 irc_test_runner.py --binary ../ircserv 2>/dev/null || \
	python3 irc_test_runner.py

# Full test with valgrind memory checking
.PHONY: valgrind
valgrind:
	@echo "$(CYAN)🔍 Running full test with memory leak detection...$(NC)"
	@python3 irc_test_runner.py --binary ./ircserv --valgrind --tester v2 2>/dev/null || \
	python3 irc_test_runner.py --valgrind

# Test both v1 and v2 testers
.PHONY: full
full:
	@echo "$(CYAN)🎯 Running comprehensive tests (v1 + v2)...$(NC)"
	@echo "$(YELLOW)Testing with v1 tester...$(NC)"
	@python3 irc_test_runner.py --binary ./ircserv --tester v1 --out results_v1 2>/dev/null || true
	@echo "$(YELLOW)Testing with v2 tester...$(NC)"
	@python3 irc_test_runner.py --binary ./ircserv --tester v2 --out results_v2 2>/dev/null || true
	@echo "$(GREEN)✅ Comprehensive testing completed!$(NC)"

# Interactive mode (force)
.PHONY: interactive
interactive:
	@echo "$(CYAN)🎮 Starting interactive mode...$(NC)"
	@python3 irc_test_runner.py --interactive

# Clean up test results
.PHONY: clean
clean:
	@echo "$(YELLOW)🧹 Cleaning up test results...$(NC)"
	@rm -rf test_results_* results_v1 results_v2 runs/
	@echo "$(GREEN)✅ Cleanup completed!$(NC)"

# Check system requirements
.PHONY: check
check:
	@echo "$(CYAN)🔍 Checking system requirements...$(NC)"
	@python3 --version || echo "$(RED)❌ Python3 not found$(NC)"
	@python3 -c "import tkinter" 2>/dev/null && echo "$(GREEN)✅ GUI support available$(NC)" || \
	echo "$(YELLOW)⚠️  GUI file picker not available$(NC)"
	@which valgrind >/dev/null 2>&1 && echo "$(GREEN)✅ Valgrind available$(NC)" || \
	echo "$(YELLOW)⚠️  Valgrind not found - install with: sudo apt install valgrind$(NC)"
	@ls -la irc_super_tester*.py 2>/dev/null && echo "$(GREEN)✅ Testers found$(NC)" || \
	echo "$(YELLOW)⚠️  No testers found in current directory$(NC)"

# Show help
.PHONY: help
help:
	@echo "$(BOLD)$(CYAN)🚀 ft_irc Test Runner - Available Commands$(NC)"
	@echo ""
	@echo "$(GREEN)make$(NC) or $(GREEN)make test$(NC)     - Run interactive test runner (recommended)"
	@echo "$(GREEN)make quick$(NC)              - Quick test with auto-detection"
	@echo "$(GREEN)make valgrind$(NC)           - Full test with memory leak detection"
	@echo "$(GREEN)make full$(NC)               - Test with both v1 and v2 testers"
	@echo "$(GREEN)make interactive$(NC)        - Force interactive mode"
	@echo "$(GREEN)make clean$(NC)              - Clean up test result files"
	@echo "$(GREEN)make check$(NC)              - Check system requirements"
	@echo "$(GREEN)make help$(NC)               - Show this help message"
	@echo ""
	@echo "$(YELLOW)💡 For first-time users: just run '$(GREEN)make$(NC)$(YELLOW)' and follow the prompts!$(NC)"

# Advanced: debug mode
.PHONY: debug
debug:
	@echo "$(CYAN)🐛 Running in debug mode...$(NC)"
	@python3 irc_test_runner.py --verbose --timeout 30

# Shortcut aliases
.PHONY: t q v f c h i
t: test
q: quick
v: valgrind  
f: full
c: clean
h: help
i: interactive
