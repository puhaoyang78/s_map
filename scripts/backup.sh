#!/bin/bash
# 功能：my-map-app 精准备份脚本 | 跳过超大DB文件 | 自选是否备份探测结果 | 实时进度
# 存放路径：/home/ubuntu/my-map-app/scripts/backup.sh
#
# ⚠️ 重要：本脚本【不备份数据库】——第 12 行固定排除 backend/data/global_device_*.db，
#    活动数据库不在备份内容内。发布前的正式备份（含数据库与 manifest 校验）请使用：
#      python scripts/backup_runtime.py --include-env
# ⚠️ SOURCE_DIR 为硬编码路径；部署目录变更时需同步修改。
set -euo pipefail

# ===================== 基础配置（无需修改）=====================
SOURCE_DIR="/home/ubuntu/my-map-app"  # 源目录（硬编码，见头部说明）
BACKUP_DIR="/home/ubuntu/my-map-backup-$(date +%Y%m%d_%H%M%S)"  # 带时间戳的备份目录
EXCLUDE_PATTERN="--exclude=backend/data/global_device_*.db"  # 固定跳过超大DB文件（即不备份数据库）

# ===================== 交互选择：是否备份终端探测结果 =====================
clear || true
echo "=============================================="
echo "          my-map-app 备份工具"
echo "=============================================="
echo "📌 固定规则：自动跳过 4个4G+ 超大DB文件（不含数据库）"
echo "📌 需您选择：是否备份【终端探测结果】(vul_scan目录CSV文件)"
echo -e "\n请选择："
echo "1) 不备份探测结果（体积更小，备份更快）"
echo "2) 备份探测结果（完整备份）"
read -p "请输入数字 1 或 2：" CHOICE

# 根据选择添加排除规则
case $CHOICE in
    1)
        echo -e "\n✅ 已选择：跳过终端探测结果"
        EXCLUDE_PATTERN+=" --exclude=front/public/data/vul_scan/* --exclude=front/dist/data/vul_scan/*"
        ;;
    2)
        echo -e "\n✅ 已选择：完整备份所有文件（含探测结果）"
        ;;
    *)
        echo -e "\n❌ 输入错误，默认跳过探测结果"
        EXCLUDE_PATTERN+=" --exclude=front/public/data/vul_scan/* --exclude=front/dist/data/vul_scan/*"
        ;;
esac

# ===================== 开始备份（带实时进度） =====================
echo -e "\n⏳ 开始备份，目标目录：$BACKUP_DIR"
echo "=============================================="

# rsync 备份：带进度、保留权限、递归、显示详情；失败必须明确报错，不得伪装成功
if ! rsync -av --progress $EXCLUDE_PATTERN "$SOURCE_DIR/" "$BACKUP_DIR/"; then
    echo -e "\n❌ 备份失败：rsync 未成功完成，请检查上方错误输出" >&2
    exit 1
fi

# ===================== 备份完成提示 =====================
echo -e "\n=============================================="
echo "🎉 备份全部完成！"
echo "📂 备份路径：$BACKUP_DIR"
echo "⚠️ 提醒：本备份不含数据库；发布前请另行运行 scripts/backup_runtime.py"
echo "=============================================="
