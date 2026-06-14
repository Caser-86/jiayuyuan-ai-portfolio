# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
