# -*- coding: utf-8 -*-
import os
import json
import shutil
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="贾玉元个人主页后端管理系统",
    description="基于 FastAPI 构建，提供项目数据读取与修改、图像文件上传和留言板管理功能。"
)

# CORS 限制为指定域名（生产环境）
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://127.0.0.1:8000,http://localhost:8000,https://libaweiyu.xyz"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传文件大小限制：5MB
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

# 限流相关（提前定义，供登录接口使用）
from collections import defaultdict
import time as _time

_rate_limit_store: Dict[str, list] = defaultdict(list)
RATE_LIMIT_MAX = 60
RATE_LIMIT_WINDOW = 60  # 秒

# 基础文件目录路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
MESSAGES_FILE = os.path.join(DATA_DIR, "messages.json")

# 管理后台默认访问密码（优先从环境变量读取）
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# 确保文件夹存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)


# ==========================================
# 辅助函数：数据读取与写入
# ==========================================
def read_json_file(file_path: str, default_value: Any) -> Any:
    """读取指定路径的 JSON 数据文件，如果不存在则使用默认值并保存"""
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(default_value, f, ensure_ascii=False, indent=2)
        return default_value
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"读取文件 {file_path} 错误: {e}")
        return default_value


def write_json_file(file_path: str, data: Any):
    """向指定路径写入 JSON 数据（写入前自动备份）"""
    # 备份旧文件
    if os.path.exists(file_path):
        backup_path = file_path + ".bak"
        try:
            shutil.copy2(file_path, backup_path)
        except Exception:
            pass
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==========================================
# 鉴权依赖项
# ==========================================
def verify_admin(x_admin_password: str = Header(None)):
    """验证后台密码，如果不匹配则抛出 401 错误"""
    if not x_admin_password or x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="管理员密码错误，未授权访问")
    return True


# ==========================================
# 数据模型定义 (Request Schema)
# ==========================================
class ProjectUpdateSchema(BaseModel):
    title: str
    tags: List[str]
    client: str
    duration: str
    tech: str
    context: str
    techDetails: str
    outcome: str


class MessageCreateSchema(BaseModel):
    name: str
    email: str
    project_type: str
    budget: str
    message: str


# ==========================================
# 1. 静态页面路由托管
# ==========================================
@app.get("/", response_class=FileResponse)
def get_home_page():
    """返回个人网站主页 index.html"""
    html_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    raise HTTPException(status_code=404, detail="未找到 index.html 文件")


@app.get("/admin", response_class=FileResponse)
def get_admin_page():
    """返回后台管理页面 admin.html"""
    html_path = os.path.join(BASE_DIR, "admin.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    raise HTTPException(status_code=404, detail="未找到 admin.html 文件")


# 挂载 assets 静态资源目录（图片等）
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


# ==========================================
# 2. 鉴权 API 路由
# ==========================================
@app.post("/api/admin/login")
def admin_login(payload: dict, request: Request):
    """后台登录验证接口（带频率限制：每 IP 每分钟最多 10 次）"""
    # 简单限流：登录接口限制更严
    client_ip = request.client.host if request.client else "unknown"
    now = _time.time()
    login_requests = _rate_limit_store.get(f"login:{client_ip}", [])
    _rate_limit_store[f"login:{client_ip}"] = [t for t in login_requests if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[f"login:{client_ip}"]) >= 10:
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请 1 分钟后再试")
    _rate_limit_store[f"login:{client_ip}"].append(now)

    password = payload.get("password")
    if password == ADMIN_PASSWORD:
        return {"success": True, "message": "登录验证成功"}
    return JSONResponse(status_code=401, content={"success": False, "message": "管理员密码错误，请重试"})


# ==========================================
# 3. 项目 API 路由 (Projects CRUD)
# ==========================================
@app.get("/api/projects")
def get_projects():
    """获取所有 6 个项目的数据"""
    return read_json_file(PROJECTS_FILE, [])


@app.post("/api/projects/{project_id}")
def update_project(project_id: int, project_data: ProjectUpdateSchema, authenticated: bool = Depends(verify_admin)):
    """更新某个具体的项目信息（需要管理员密码鉴权）"""
    projects = read_json_file(PROJECTS_FILE, [])
    
    # 查找匹配的项目
    target_index = -1
    for i, p in enumerate(projects):
        if p.get("id") == project_id:
            target_index = i
            break
            
    if target_index == -1:
        raise HTTPException(status_code=404, detail=f"未找到 ID 为 {project_id} 的项目")
        
    # 保留原项目的图片、ID 和 images 数组，仅更新表单提交字段
    updated_project = {
        "id": project_id,
        "title": project_data.title,
        "tags": project_data.tags,
        "client": project_data.client,
        "duration": project_data.duration,
        "tech": project_data.tech,
        "img": projects[target_index].get("img", f"assets/project{project_id + 1}.png"),
        "images": projects[target_index].get("images", [f"assets/project{project_id + 1}.png"]),
        "context": project_data.context,
        "techDetails": project_data.techDetails,
        "outcome": project_data.outcome
    }
    
    projects[target_index] = updated_project
    write_json_file(PROJECTS_FILE, projects)
    
    return {"success": True, "message": f"项目 ID {project_id} 信息已成功更新"}


# ==========================================
# 4. 图像上传 API 路由 (Image Upload)
# ==========================================
@app.post("/api/upload")
async def upload_image(
    file: UploadFile = File(...),
    image_type: str = Form(...),
    authenticated: bool = Depends(verify_admin)
):
    """
    上传图像接口（需要管理员密码鉴权）
    根据 image_type 的值保存文件：
    - avatar → avatar.png
    - hero_bg → hero_bg.png
    - projectN → projectN.png（覆盖主图）
    - projectN_extra → projectN_{M}.png（追加额外图片）
    """
    # 文件大小校验
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"文件过大，最大允许 {MAX_UPLOAD_SIZE // 1024 // 1024}MB")

    # 文件扩展名校验
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式，仅允许：{', '.join(sorted(ALLOWED_EXTENSIONS))}")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="上传的文件类型错误，必须为图片格式")

    # 解析 image_type: project1_extra → (project_idx=1, is_extra=True)
    is_extra = image_type.endswith("_extra")
    base_type = image_type.replace("_extra", "") if is_extra else image_type

    filename = ""
    if base_type == "avatar":
        filename = "avatar.png"
    elif base_type == "hero_bg":
        filename = "hero_bg.png"
    elif base_type in [f"project{i}" for i in range(1, 7)]:
        if is_extra:
            # 计算下一个序号
            proj_idx = int(base_type.replace("project", ""))
            projects = read_json_file(PROJECTS_FILE, [])
            proj = next((p for p in projects if p["id"] == proj_idx - 1), None)
            existing = proj.get("images", []) if proj else []
            next_num = len(existing)  # 从第2张开始（索引1）
            filename = f"project{proj_idx}_{next_num}.png"
            # 更新 projects.json
            if proj:
                if "images" not in proj:
                    proj["images"] = [f"assets/project{proj_idx}.png"]
                proj["images"].append(f"assets/{filename}")
                write_json_file(PROJECTS_FILE, projects)
        else:
            filename = f"{base_type}.png"
    else:
        raise HTTPException(status_code=400, detail="未知的图片类型分类，无法保存")

    target_path = os.path.join(ASSETS_DIR, filename)

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"success": True, "message": f"图片已成功上传为 {filename}", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存图片文件失败: {str(e)}")


@app.delete("/api/projects/{project_id}/images/{img_filename}")
async def delete_project_image(
    project_id: int,
    img_filename: str,
    authenticated: bool = Depends(verify_admin)
):
    """删除项目的某张额外图片"""
    # 路径穿越防护：只允许合法文件名
    if ".." in img_filename or "/" in img_filename or "\\" in img_filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    projects = read_json_file(PROJECTS_FILE, [])
    proj = next((p for p in projects if p["id"] == project_id), None)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")

    images = proj.get("images", [])
    # 保留第一张主图，不能删除
    if len(images) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一张主图")

    # 兼容两种格式：纯文件名 或 带 assets/ 前缀
    target = img_filename if img_filename.startswith("assets/") else f"assets/{img_filename}"
    if target not in images:
        raise HTTPException(status_code=404, detail="图片不在项目列表中")

    # 删除文件（确保路径在 ASSETS_DIR 内）
    safe_filename = os.path.basename(img_filename)
    file_path = os.path.join(ASSETS_DIR, safe_filename)
    if os.path.exists(file_path) and os.path.realpath(file_path).startswith(os.path.realpath(ASSETS_DIR)):
        os.remove(file_path)

    images.remove(target)
    write_json_file(PROJECTS_FILE, projects)
    return {"success": True, "message": f"已删除 {img_filename}"}


# ==========================================
# 5. 留言 API 路由 (Messages Management)
# ==========================================
@app.post("/api/messages")
def create_message(message_data: MessageCreateSchema):
    """用户提交联系留言意向，写入本地 JSON"""
    messages = read_json_file(MESSAGES_FILE, [])
    
    # 构建留言对象，补充提交时间
    new_message = {
        "id": len(messages) + 1,
        "name": message_data.name,
        "email": message_data.email,
        "project_type": message_data.project_type,
        "budget": message_data.budget,
        "message": message_data.message,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    messages.append(new_message)
    write_json_file(MESSAGES_FILE, messages)
    return {"success": True, "message": "留言意向已成功发送，感谢您的联系！"}


@app.get("/api/messages")
def get_messages(authenticated: bool = Depends(verify_admin)):
    """管理员获取所有收到的客户留言（需要管理员密码鉴权）"""
    messages = read_json_file(MESSAGES_FILE, [])
    # 按时间降序排列，最新提交的排在最前
    messages.reverse()
    return messages


TESTIMONIALS_FILE = os.path.join(DATA_DIR, "testimonials.json")


@app.get("/api/testimonials")
def get_testimonials():
    """获取客户评价配置（公开接口，前端根据 enabled 决定是否显示）"""
    return read_json_file(TESTIMONIALS_FILE, {"enabled": False, "items": []})


@app.post("/api/testimonials")
def update_testimonials(
    payload: Dict[str, Any],
    authenticated: bool = Depends(verify_admin)
):
    """更新客户评价配置（需要管理员密码鉴权）"""
    write_json_file(TESTIMONIALS_FILE, payload)
    return {"success": True, "message": "客户评价配置已更新"}


# ==========================================
# 6. 基本信息 API 路由 (Profile Management)
# ==========================================
PROFILE_FILE = os.path.join(DATA_DIR, "profile.json")


@app.get("/api/profile")
def get_profile():
    """获取基本信息（公开接口，前端展示用）"""
    return read_json_file(PROFILE_FILE, {})


@app.post("/api/profile")
def update_profile(
    payload: Dict[str, Any],
    authenticated: bool = Depends(verify_admin)
):
    """更新基本信息（需要管理员密码鉴权）"""
    data = {
        "email": payload.get("email", ""),
        "wechat": payload.get("wechat", ""),
        "wechatNote": payload.get("wechatNote", ""),
        "status": payload.get("status", ""),
        "statusEn": payload.get("statusEn", ""),
        "socials": payload.get("socials", [])
    }
    write_json_file(PROFILE_FILE, data)
    return {"success": True, "message": "基本信息已更新"}


# ==========================================
# 7. 辅助路由 (Health / robots.txt / sitemap / 404)
# ==========================================


@app.get("/health")
def health_check():
    """健康检查接口（监控用）"""
    return {"status": "ok", "version": "0.1.3"}


@app.get("/robots.txt")
def robots_txt():
    """搜索引擎爬虫控制"""
    content = "User-agent: *\nAllow: /\nSitemap: https://libaweiyu.xyz/sitemap.xml\n"
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml")
def sitemap_xml():
    """SEO 站点地图"""
    content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://libaweiyu.xyz/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <url><loc>https://libaweiyu.xyz/#portfolio</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>https://libaweiyu.xyz/#skills</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>
  <url><loc>https://libaweiyu.xyz/#contact</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>
</urlset>"""
    return Response(content=content, media_type="application/xml")


@app.exception_handler(404)
async def not_found_handler(request, exc):
    """自定义 404 页面"""
    return JSONResponse(
        status_code=404,
        content={"detail": "页面未找到", "message": "请求的资源不存在"}
    )
