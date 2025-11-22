# 📚 Book Finder

自动化书籍查找工具：从 Notion 获取想读书单，在微信读书上搜索，使用 LLM 智能判断书籍上架状态，并发送通知。

## 🚀 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
conda create -n book-finder python=3.11
conda activate book-finder

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

#### 2.1 获取 Notion Database ID

```bash
python tools/get_notion_db_id.py
```

复制你的"我的想读"数据库 ID。

#### 2.2 配置文件

编辑 `config/config.yaml`：

```yaml
notion:
  api_token: "your_notion_token"
  database_id: "your_database_id"

llm:
  base_url: "https://cloud.infini-ai.com/maas/v1"
  api_key: "your_api_key"
  model: "claude-sonnet-4-5-20250929"

notification:
  feishu_webhook: "your_webhook_url"  # 可选
  wecom_webhook: ""  # 可选
  enabled_channels: ["feishu"]
```

#### 2.3 初始化 Notion 数据库

```bash
python tools/init_database.py
```

这会自动添加所需的列：作者、ISBN、状态、已上架、最后检查时间、搜索关键词、备注。

### 3. 运行

#### 手动运行

```bash
python run.py
```

#### 定时任务

```bash
# 编辑配置文件中的 scheduler.cron
python scheduler.py
```

或使用 Docker：

```bash
docker-compose up -d
```

## 📋 Notion 数据库字段

| 字段 | 类型 | 说明 |
|------|------|------|
| Name（书名） | 标题 | 必需，书籍名称 |
| 作者 | 文本 | 推荐，提高搜索准确度 |
| 状态 | 选择 | 可选，如"想读" |
| 已上架 | 复选框 | 自动更新 |
| 最后检查时间 | 日期 | 自动更新 |
| 搜索关键词 | 文本 | 自动更新 |
| 备注 | 文本 | 自动更新，LLM分析结果 |

## 🔍 工作原理

1. 从 Notion 获取待检查书籍（跳过已上架的书籍）
2. 在微信读书 API 搜索
3. 使用 LLM 分析搜索结果，判断书籍状态
   - 区分"已上架可阅读"和"待上架"状态
   - 待上架的书不算已上架
4. 更新 Notion 数据库
5. 发送飞书/企业微信通知

## 🛠️ 辅助工具

```bash
# 获取数据库 ID
python tools/get_notion_db_id.py

# 初始化数据库列
python tools/init_database.py

# 检查数据库结构
python tools/inspect_database.py
```

## ⚙️ 配置说明

### Cron 表达式

格式：`分 时 日 月 星期`

示例：
- `0 9 * * *` - 每天 9:00
- `0 */6 * * *` - 每 6 小时
- `0 9,21 * * *` - 每天 9:00 和 21:00

### 通知渠道

在 `config.yaml` 中配置：

```yaml
notification:
  wecom_webhook: "企业微信 Webhook URL"
  feishu_webhook: "飞书 Webhook URL"
  enabled_channels: ["wecom", "feishu"]  # 选择启用的渠道
```

## 📝 日志

日志文件保存在 `logs/` 目录，按日期自动轮转。

```bash
tail -f logs/book_finder_$(date +%Y-%m-%d).log
```

## 🐳 Docker 部署

```bash
# 定时任务模式
docker-compose up -d

# 手动运行
docker-compose --profile manual run --rm book-finder-manual

# 查看日志
docker-compose logs -f
```

## 📄 许可证

MIT License

