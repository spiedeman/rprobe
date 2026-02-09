#!/bin/bash
# 虚拟环境快捷管理脚本
# 使用: source venv.sh [command]

VENV_DIR=".venv"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查虚拟环境是否存在
check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${RED}❌ 虚拟环境不存在${NC}"
        echo "请先运行: python3 -m venv $VENV_DIR"
        return 1
    fi
    return 0
}

# 激活虚拟环境
activate() {
    if check_venv; then
        source "$VENV_DIR/bin/activate"
        echo -e "${GREEN}✅ 虚拟环境已激活${NC}"
        echo "Python: $(which python)"
        echo "版本: $(python --version)"
    fi
}

# 显示状态
status() {
    if [ -n "$VIRTUAL_ENV" ]; then
        echo -e "${GREEN}✅ 虚拟环境已激活${NC}"
        echo "路径: $VIRTUAL_ENV"
        echo "Python: $(which python)"
    else
        echo -e "${YELLOW}⚠️  虚拟环境未激活${NC}"
        if [ -d "$VENV_DIR" ]; then
            echo "运行 'source venv.sh activate' 激活"
        else
            echo "运行 'python3 -m venv $VENV_DIR' 创建"
        fi
    fi
}

# 安装依赖
install() {
    if [ -z "$VIRTUAL_ENV" ]; then
        echo -e "${RED}❌ 请先激活虚拟环境${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}📦 安装项目依赖...${NC}"
    pip install -e .
    
    echo -e "${YELLOW}📦 安装开发依赖...${NC}"
    pip install pytest pytest-cov black flake8 mypy pre-commit isort bandit
    
    echo -e "${GREEN}✅ 依赖安装完成${NC}"
}

# 运行测试
test() {
    if [ -z "$VIRTUAL_ENV" ]; then
        echo -e "${RED}❌ 请先激活虚拟环境${NC}"
        echo "运行: source venv.sh activate"
        return 1
    fi
    
    echo -e "${YELLOW}🧪 运行测试...${NC}"
    TESTING=true python -m pytest tests/unit -v
}

# 显示帮助
help() {
    echo "虚拟环境管理脚本"
    echo ""
    echo "用法: source venv.sh [命令]"
    echo ""
    echo "命令:"
    echo "  activate   激活虚拟环境 (默认)"
    echo "  status     查看虚拟环境状态"
    echo "  install    安装项目依赖"
    echo "  test       运行单元测试"
    echo "  help       显示此帮助"
    echo ""
    echo "示例:"
    echo "  source venv.sh           # 激活虚拟环境"
    echo "  source venv.sh activate  # 激活虚拟环境"
    echo "  source venv.sh status    # 查看状态"
    echo "  source venv.sh test      # 运行测试"
}

# 主逻辑
case "${1:-activate}" in
    activate|a)
        activate
        ;;
    status|s)
        status
        ;;
    install|i)
        install
        ;;
    test|t)
        test
        ;;
    help|h)
        help
        ;;
    *)
        echo -e "${RED}❌ 未知命令: $1${NC}"
        help
        return 1
        ;;
esac
