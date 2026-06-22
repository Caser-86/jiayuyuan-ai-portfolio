# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [v0.3.0] - 2026-06-23

### ✨ 新增

- **面试导向 Hero 区域** — 保留原背景图与头像，新增打字机副标题、关键数据展示、下载简历 CTA
- **项目成果展示** — 项目卡片可选显示绿色成果标签、量化指标栏、"在线体验"按钮
- **项目在线体验链接** — 每个项目可配置独立 `demo_url`，前端条件渲染，无链接则不显示
- **技能雷达图切换** — 技能区默认保留卡片+进度条视图，新增"能力雷达"一键切换，右侧图例展示完整描述
- **项目详情弹窗升级** — 弹窗内增加在线体验按钮和成果数据卡片，Case Study 结构更清晰

### 🔧 后端

- `ProjectCreateSchema` / `ProjectUpdateSchema` 新增可选字段：`demo_url`、`impact`、`metrics`
- 管理后台表单同步增加上述字段，`metrics` 支持 `标签: 值` 每行一个的便捷输入

---

## [v0.2.0] - 2026-06-22

### ✨ 新增

- **技能管理模块** — 后台可自由增删改排序技能，前端自适应网格布局
- **技能显隐控制** — 每个技能可单独隐藏，公开接口自动过滤并按顺序重新编号
- **项目显隐控制** — 后台可隐藏任意项目，前端只展示未隐藏项目并重新编号
- **项目 / 技能排序** — 管理后台支持上移/下移调整顺序，后端 `/api/projects/reorder` 与 `/api/skills/reorder` 持久化
- **历史项目恢复** — 将最初 6 个项目作为案例 7-12 恢复并上传对应图片
- **404 页面智能响应** — 浏览器访问返回 HTML 404 页面，API 访问返回 JSON

### 🐛 修复

- **项目排序失败** — `/api/projects/reorder` 路由被 `/api/projects/{project_id}` 覆盖导致 422，调整路由顺序后修复
- **项目图片上传数量限制** — 原代码硬编码 `project1` ~ `project12`，新增第 13 个项目后无法上传，改为正则匹配任意 `projectN`
- **创建与编辑项目 tags 校验不一致** — `ProjectCreateSchema` 允许空 tags 而 `ProjectUpdateSchema` 要求必填，统一为必填且至少 1 个
- **技能排序前端不报错** — 后端返回 400 时前端仍提示“排序已更新”，现在会正确提示 `data.detail`
- **图片 src 属性编码错误** — 使用 `escapeHtml` 会导致 URL 中 `&` 被转义，改为 `escapeAttr`
- **轮播定时器内存泄漏** — 鼠标反复悬停/离开会累积大量已清除的 `setInterval` 引用
- **`deploy-aliyun.sh` systemd 指令拼写错误** — `StandardErrorOutput` 应为 `StandardError`，导致错误日志无法写入文件
- **留言/登录限流在反向代理后失效** — 原 `request.client.host` 取到的是 Nginx 本地地址，改为优先读取 `X-Forwarded-For` / `X-Real-IP`
- **`upload_image` 回滚逻辑缺陷** — 主图上传时 JSON 先更新、文件写入失败后回滚不完整；重构为先写文件再写 JSON，任一失败均可安全回滚

### 🔧 部署改进

- **部署时保护用户数据** — `auto_deploy.py` 先备份并恢复服务器 `data/` 与 `assets/`，再用本地 `skills.json` / `projects.json` 覆盖，避免管理后台上传的图片/GitHub 地址被清空
- **服务错误日志** — 修复 `StandardError` 后，`/var/log/jiayuyuan.error.log` 正常记录 gunicorn 错误

---

## [v0.1.3] - 2026-06-14

### ✨ 新增

- **多图片轮播展示** — 每个项目支持上传多张截图，前端卡片自动轮播（10秒间隔），悬停暂停 + 左右箭头 + 圆点指示器
- **后台多图管理** — 替换主图 / 添加额外图片 / 删除图片，实时预览
- **`/api/profile` 接口** — GET 获取基本信息，POST 保存基本信息
- **`/api/testimonials` 接口** — GET/POST 支持客户评价数据读写
- **`/api/upload` 删除图片接口** — 支持删除额外图片（`DELETE /api/upload`）

### 🐛 修复

- **项目卡片 CSS 类名不匹配** — JS 生成 `card-content/card-tags`，CSS 定义 `portfolio-info/portfolio-tags`，导致文字无样式
- **上传按钮点击无效** — `lucide.createIcons()` 把 `<i>` 替换为 SVG 后拦截 `<label>` 点击，改用 `<button>` + JS 触发
- **`showToast` 报错 `Cannot read properties of null`** — `querySelector('i')` 返回 null，改用 `<span>` 容器
- **项目分类筛选失效** — 前端用数组索引而非 `proj.id` 计算分类，顺序错乱时错位
- **删除按钮无效** — `onclick` 中文件名含特殊字符导致 JS 语法错误，改用 `data-*` 属性 + 事件委托
- **删除 API 404** — URL 传 `project1_2.png` 但数组存 `assets/project1_2.png`，兼容两种格式
- **上传额外图片后预览不刷新** — 上传完成后自动调用 `fetchProjects()` 刷新面板
- **客户评价轮播隐藏时白跑定时器** — 改为按需启动
- **表单校验失败不滚动** — 移动端看不到错误提示，添加 `scrollIntoView`
- **项目4描述拼写错误** — "预先加载 of 行业标准" → "预先加载的行业标准"
- **社交图标 `twitter-x` 无效** — Lucide 无此图标名，改为 `twitter`
- **项目5 `img` → `images` 字段遗漏** — 统一为 `images` 数组

### 🔒 安全加固

- CORS 限制为指定域名
- 上传文件大小限制 5MB + 扩展名校验
- 登录接口频率限制（每 IP 每分钟 10 次）
- 管理员密码改为环境变量读取
- JSON 写入前自动 `.bak` 备份
- 删除图片路径穿越防护
- 社交链接 `sanitizeUrl` XSS 防护
- CDN 脚本版本锁定 `lucide@1.17.0`
- 依赖版本锁定（`>=` → `==`）

### 🧪 新增接口

- `GET /health` — 健康检查
- `GET /robots.txt` — SEO 支持
- `GET /sitemap.xml` — 搜索引擎站点地图
- 自定义 404 JSON 响应

---

## [v0.1.2] - 2026-06-14

### 🐛 修复

- **`/api/testimonials` 接口缺失** — 前端调用返回 404，客户评价模块无法启用
- **项目分类筛选失效** — `inferCategory` 逻辑错误，RPA/n8n 被错误归类为 `data-analysis`
- **管理员密码硬编码** — 改为从环境变量 `ADMIN_PASSWORD` 读取
- **CDN 脚本版本未锁定** — `lucide@latest` → `lucide@1.17.0`
- **上传无文件大小限制** — 添加 5MB 上限校验
- **上传无文件扩展名校验** — 仅允许 `.png/.jpg/.jpeg/.webp/.gif/.bmp`
- **CORS 全开** — 限制为指定域名（可通过 `ALLOWED_ORIGINS` 环境变量配置）
- **依赖版本未锁定** — `>=` → `==` 精确匹配
- **无健康检查接口** — 添加 `/health`
- **无 robots.txt / sitemap.xml** — 添加 SEO 支持
- **无 404 错误页面** — 添加自定义 404 JSON 响应
- **轮播定时器内存泄漏** — 页面卸载时清理所有 `setInterval`
- **拖拽上传用 `window.prompt`** — 改用自定义弹窗选择上传位置
- **社交链接编辑器 XSS 风险** — URL 字段添加 `sanitizeUrl` 防护
- **JSON 数据无备份** — 写入前自动创建 `.bak` 备份文件
- **登录接口无频率限制** — 每 IP 每分钟最多 10 次登录尝试

### 🧪 测试

- **供应链安全检查**
  - 添加 `tests/test_supply_chain_static.py`
  - 检查 CDN 脚本版本锁定和完整性校验
  - 验证 Python 依赖精确版本锁定
  - 检查部署脚本无未锁定包安装

---

## [v0.1.1] - 2026-06-10

### 🐛 修复

- **项目卡片图片显示**
  - `object-fit: cover` → `contain`（图片完整显示，不再被裁切）
  - 动态 `aspect-ratio` 适配图片自自然比例（零留白）
  - 最终采用最稳定的 `width: 100%; height: auto` 方案
- **图片上传缓存**
  - 自定义 `NoCacheStaticFiles` 中间件：直接在静态资源响应中追加 `Cache-Control: no-store, no-cache, must-revalidate`
  - 解决 FastAPI StaticFiles 绕过 HTTP middleware 导致 no-cache 头不生效的问题
  - 涵盖 project/avatar/hero_bg/wechat_qr 前缀的所有图片
- **项目 1 缩略图上传**
  - 放宽文件选择器 `accept` 属性（支持更多图片格式）
  - 完整诊断 + Python 脚本兜底上传路径
- **基本信息设置面板** — 修复 JS 引用 `panel-profile` 但 HTML 元素不存在的问题
- **客户评价模块** — 后端 `enabled` 字段控制显隐，前端 CSS + JS 双重防御

### ✨ 新增

- **全局拖拽上传**：把图片文件直接拖到 admin 页面任意位置 → 弹窗选上传位置 → 完成
- **Git 版本管理**：初始化本地仓库，添加 .gitignore / README / CHANGELOG

### 🎨 体验优化

- 导航栏添加半透明白底 + 模糊效果（提高文字可读性）
- 上传图片 URL 自动加 `?v=Date.now()` 时间戳防缓存
- admin 后台文件选择器放宽图片格式限制

---

## [v0.1.0] - 2026-06-10

### ✨ 新增

- 🏠 **个人主页前端** (`index.html`)
  - Hero 区域 + 精选作品 + 服务模块 + 客户评价 + 关于合作 + 联系方式
  - 项目卡片（缩略图 + 标签 + 标题 + 摘要）
  - 项目详情弹窗（描述 / 标签 / 链接）
  - 留言板表单
  - 微信二维码弹窗（动态加载）
  - 响应式布局
- ⚙️ **后台管理界面** (`admin.html`)
  - 项目管理（CRUD）
  - 留言管理（查看 / 删除 / 一键清空）
  - 基本信息设置（姓名 / 头衔 / 简介 / 头像 / 微信）
  - 客户评价管理（启用 / 关闭）
  - 全局拖拽上传（支持鼠标拖拽图片到页面任意位置）
- 🔧 **FastAPI 后端** (`main.py`)
  - 项目 / 留言 / 个人信息 / 客户评价 CRUD API
  - 文件上传接口（项目缩略图 / 头像 / 背景 / 二维码）
  - 管理员鉴权（`X-Admin-Password` Header）
  - 自定义 `NoCacheStaticFiles` 中间件（强制 `no-cache` 头，避免浏览器缓存）
  - CORS 跨域支持
- 📦 **数据存储** (`data/`)
  - `projects.json` — 项目列表
  - `messages.json` — 留言列表
  - `profile.json` — 个人信息
  - `testimonials.json` — 客户评价（`enabled` 开关 + `items` 列表）
- 🚀 **部署支持**
  - `auto_deploy.py` — 阿里云 ECS 自动化部署脚本
  - `deploy-aliyun.sh` — Linux 端部署 Shell（Python 3.11 + Nginx + Systemd）
  - `requirements.txt` — Python 依赖锁定
  - `implementation_plan.md` — 项目实现计划文档
- 📝 **文档**
  - README.md
  - CHANGELOG.md（本文件）
  - .gitignore

### 🎨 视觉设计

- 深色主题（主色：`#6366f1` 靛蓝 / `#0f172a` 深蓝灰）
- 玻璃拟态卡片（`backdrop-filter: blur(20px)`）
- Lucide Icons 图标库
- 渐变背景 + 动效
- 平滑过渡与悬停反馈

### 🐛 已修复

- 浏览器缓存导致上传图片看不到效果
- StaticFiles 中间件绕过 HTTP middleware 导致 `Cache-Control` 头不生效
- 文件选择器 `accept` 限制过严导致部分图片无法上传
- 微信二维码弹窗显示硬编码微信号（已改为后端动态加载）

---

## [未发布]

### 计划中

- 📱 移动端优化
- 🌓 浅色主题切换
- 📊 访问统计（PV / UV）
- 🗂️ 多语言支持
- 🔍 项目搜索 / 筛选
