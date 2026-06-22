# 贾玉元.AI · 个人主页

> 一个现代化的 AI 产品经理 / 独立开发者个人主页，含前后端、后台管理与阿里云部署。

![Version](https://img.shields.io/badge/version-v0.3.1-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal)
![License](https://img.shields.io/badge/license-MIT-orange)

## ✨ 功能

- 🏠 **个人主页** — 精选作品、服务、关于合作、联系方式
- ⚙️ **管理后台** — 项目、技能、留言、基本信息、图像上传
- 🖼️ **图像管理** — 缩略图 / 头像 / 背景 / 二维码，本地存储
- 💬 **留言板** — 访客留言 + 后台审核管理
- 📦 **模块化** — 客户评价 / 关于合作等模块后端可控
- 🎭 **显隐控制** — 项目 / 技能可在后台隐藏，前端自动过滤并重排序号
- 🔀 **拖拽排序** — 项目 / 技能支持排序，前端布局自适应数量
- 🎯 **面试导向首页** — Hero 打字机、关键数据、下载简历 CTA
- 📊 **项目成果展示** — 成果标签、量化指标、在线体验链接
- 🕸️ **技能雷达图** — 卡片视图与能力雷达图一键切换
- 🚀 **一键部署** — Aliyun ECS 自动化部署脚本
- 🔒 **缓存控制** — 自定义静态文件中间件保证修改即时可见

## 🛠️ 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + Uvicorn |
| 前端 | 原生 HTML / CSS / JavaScript（无框架） |
| 数据 | JSON 文件存储（data/ 目录） |
| 部署 | Alibaba Cloud Linux 3 + Nginx + Systemd |
| HTTPS | Let's Encrypt |
| 图标 | Lucide Icons |

## 📂 目录结构

```
D:\Files\备用\
├── main.py                # FastAPI 后端主程序
├── index.html             # 个人主页（前端展示）
├── admin.html             # 后台管理界面
├── requirements.txt       # Python 依赖
├── implementation_plan.md # 项目实现计划
├── README.md              # 项目说明文档
├── CHANGELOG.md           # 版本更新日志
├── .gitignore             # Git 忽略规则
├── data/                  # JSON 数据存储
│   ├── projects.json
│   ├── skills.json
│   ├── messages.json
│   ├── profile.json
│   └── testimonials.json
├── assets/                # 静态资源
│   ├── project1.png ... project12.png
│   ├── avatar.png
│   ├── hero_bg.png
│   └── wechat_qr.png
├── upload/                # 临时上传目录（不入版本）
├── auto_deploy.py         # 阿里云自动化部署脚本
├── deploy-aliyun.sh       # 阿里云 ECS 部署 Shell
└── deploy.ps1             # Windows PowerShell 部署脚本
```

## 🚀 本地启动

```bash
# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动服务（默认 8000 端口）
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

访问：
- 首页：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- 后台：[http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 🌐 部署到阿里云 ECS

```bash
python auto_deploy.py
```

自动完成：上传代码 → 安装 Python 3.11 → 创建虚拟环境 → 安装依赖 → 配置 Nginx → 配置 Systemd 服务 → 启动。

## 📝 版本

当前版本：**v0.3.1**（首页 Hero 后台可配置 + 统计数字与按钮可开关）

详见 [CHANGELOG.md](CHANGELOG.md)。

## 👤 作者

**贾玉元** · AI 产品经理 / 独立开发者
- GitHub：[@Caser-86](https://github.com/Caser-86)
- 邮箱：776706958@qq.com
- 域名：libaweiyu.xyz

## 📄 协议

MIT License
