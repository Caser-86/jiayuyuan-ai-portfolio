# -*- coding: utf-8 -*-
import os
import json
import shutil
import threading
import secrets
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# 文件写入锁，防止并发写入导致数据丢失
_file_lock = threading.Lock()

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
RATE_LIMIT_WINDOW = 60  # 秒
_last_cleanup: float = _time.time()
_CLEANUP_INTERVAL = 300  # 每 5 分钟清理一次过期条目


def _get_client_ip(request: Request) -> str:
    """获取真实客户端 IP，优先读取反向代理传递的头部"""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("x-real-ip")
    if xri:
        return xri.strip()
    return request.client.host if request.client else "unknown"


def _cleanup_rate_limit_store():
    """定期清理过期的限流记录，防止内存泄漏"""
    global _last_cleanup
    now = _time.time()
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    expired_keys = [k for k, v in _rate_limit_store.items() if not any(now - t < RATE_LIMIT_WINDOW for t in v)]
    for k in expired_keys:
        del _rate_limit_store[k]

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
def read_json_file(file_path: str, default_value: Any, _locked: bool = False) -> Any:
    """读取指定路径的 JSON 数据文件，如果不存在则使用默认值并保存
    
    _locked: 如果为 True，表示调用方已持有 _file_lock，不再次加锁
    """
    if not os.path.exists(file_path):
        # 如果调用方未持锁，则加锁；否则直接写入
        if _locked:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(default_value, f, ensure_ascii=False, indent=2)
        else:
            with _file_lock:
                # 双重检查，防止并发创建
                if not os.path.exists(file_path):
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(default_value, f, ensure_ascii=False, indent=2)
        return default_value
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[严重错误] JSON 文件损坏 {file_path}: {e}，返回默认值。请检查 .bak 备份文件恢复数据。")
        return default_value
    except Exception as e:
        print(f"读取文件 {file_path} 错误: {e}")
        return default_value


def write_json_file(file_path: str, data: Any):
    """向指定路径写入 JSON 数据（写入前自动备份，使用锁防止并发）"""
    with _file_lock:
        _write_json_unlocked(file_path, data)


def _write_json_unlocked(file_path: str, data: Any):
    """内部写入函数，调用前必须已持有 _file_lock"""
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
def verify_admin(x_admin_password: Optional[str] = Header(None)):
    """验证后台密码，如果不匹配则抛出 401 错误"""
    if not x_admin_password or not secrets.compare_digest(x_admin_password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="管理员密码错误，未授权访问")
    return True


# ==========================================
# 数据模型定义 (Request Schema)
# ==========================================
class ProjectCreateSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    tags: List[str] = Field(..., min_length=1, max_length=20)
    client: str = Field(default="", max_length=100)
    duration: str = Field(default="", max_length=50)
    tech: str = Field(default="", max_length=500)
    context: str = Field(default="", max_length=2000)
    techDetails: str = Field(default="", max_length=3000)
    outcome: str = Field(default="", max_length=2000)
    github_url: str = Field(default="", max_length=500)
    demo_url: str = Field(default="", max_length=500)
    impact: str = Field(default="", max_length=100)
    metrics: List[Dict[str, str]] = Field(default=[], max_length=10)
    hidden: bool = Field(default=False)


class ProjectUpdateSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    tags: List[str] = Field(..., min_length=1, max_length=20)
    client: str = Field(..., max_length=100)
    duration: str = Field(..., max_length=50)
    tech: str = Field(..., max_length=500)
    context: str = Field(..., max_length=2000)
    techDetails: str = Field(..., max_length=3000)
    outcome: str = Field(..., max_length=2000)
    github_url: str = Field(default="", max_length=500)
    demo_url: str = Field(default="", max_length=500)
    impact: str = Field(default="", max_length=100)
    metrics: List[Dict[str, str]] = Field(default=[], max_length=10)
    hidden: bool = Field(default=False)


class MessageCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=5, max_length=200)
    project_type: str = Field(..., min_length=1, max_length=50)
    budget: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=10, max_length=2000)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('邮箱格式不正确')
        return v


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


@app.get("/admin.html")
def redirect_admin_html():
    """将 /admin.html 重定向到 /admin"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/admin", status_code=301)


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
    # 定期清理过期限流记录
    _cleanup_rate_limit_store()
    # 简单限流：登录接口限制更严
    client_ip = _get_client_ip(request)
    now = _time.time()
    login_requests = _rate_limit_store.get(f"login:{client_ip}", [])
    _rate_limit_store[f"login:{client_ip}"] = [t for t in login_requests if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[f"login:{client_ip}"]) >= 10:
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请 1 分钟后再试")
    _rate_limit_store[f"login:{client_ip}"].append(now)

    password = payload.get("password") if isinstance(payload, dict) else None
    if password is None or not isinstance(password, str):
        return JSONResponse(status_code=401, content={"success": False, "message": "请提供密码"})
    if secrets.compare_digest(password, ADMIN_PASSWORD):
        return {"success": True, "message": "登录验证成功"}
    return JSONResponse(status_code=401, content={"success": False, "message": "管理员密码错误，请重试"})


# ==========================================
# 3. 项目 API 路由 (Projects CRUD)
# ==========================================
@app.get("/api/projects")
def get_projects():
    """获取所有未隐藏的项目（前端公开接口，按隐藏状态过滤并重新编号显示序号）"""
    all_projects = read_json_file(PROJECTS_FILE, [])
    visible = [p for p in all_projects if not p.get("hidden", False)]
    # 重新编号 display_id（从0开始连续）
    for i, p in enumerate(visible):
        p["display_id"] = i
    return visible


@app.get("/api/admin/projects")
def get_admin_projects(authenticated: bool = Depends(verify_admin)):
    """获取所有项目包括已隐藏的（管理后台接口）"""
    return read_json_file(PROJECTS_FILE, [])


@app.post("/api/projects")
def create_project(project_data: ProjectCreateSchema, authenticated: bool = Depends(verify_admin)):
    """创建新项目（需要管理员密码鉴权）"""
    with _file_lock:
        projects = read_json_file(PROJECTS_FILE, [], _locked=True)
        new_id = len(projects)
        new_project = {
            "id": new_id,
            "title": project_data.title,
            "tags": project_data.tags,
            "client": project_data.client,
            "duration": project_data.duration,
            "tech": project_data.tech,
            "img": f"assets/project{new_id + 1}.png",
            "images": [f"assets/project{new_id + 1}.png"],
            "context": project_data.context,
            "techDetails": project_data.techDetails,
            "outcome": project_data.outcome,
            "github_url": project_data.github_url,
            "hidden": project_data.hidden
        }
        projects.append(new_project)
        _write_json_unlocked(PROJECTS_FILE, projects)

    return {"success": True, "message": f"项目已成功创建", "id": new_id}


class ReorderRequest(BaseModel):
    """项目排序请求体"""
    order: list[int]  # 项目 ID 的新顺序


@app.post("/api/projects/reorder")
def reorder_projects(req: ReorderRequest, authenticated: bool = Depends(verify_admin)):
    """按指定顺序重新排列项目（需要管理员密码鉴权）"""
    with _file_lock:
        projects = read_json_file(PROJECTS_FILE, [], _locked=True)
        project_map = {p["id"]: p for p in projects}
        # 按新顺序重组
        new_projects = []
        for new_idx, pid in enumerate(req.order):
            if pid not in project_map:
                raise HTTPException(status_code=400, detail=f"项目 ID {pid} 不存在")
            proj = project_map[pid]
            proj["id"] = new_idx
            new_projects.append(proj)
        _write_json_unlocked(PROJECTS_FILE, new_projects)

    return {"success": True, "message": "项目顺序已成功更新"}


@app.post("/api/projects/{project_id}")
def update_project(project_id: int, project_data: ProjectUpdateSchema, authenticated: bool = Depends(verify_admin)):
    """更新某个具体的项目信息（需要管理员密码鉴权）"""
    # 原子操作：读取-修改-写入在同一个锁内完成
    with _file_lock:
        projects = read_json_file(PROJECTS_FILE, [], _locked=True)
        
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
            "outcome": project_data.outcome,
            "github_url": project_data.github_url,
            "hidden": project_data.hidden
        }
        
        projects[target_index] = updated_project
        _write_json_unlocked(PROJECTS_FILE, projects)
    
    return {"success": True, "message": f"项目 ID {project_id} 信息已成功更新"}


@app.post("/api/projects/{project_id}/toggle-hidden")
def toggle_project_hidden(project_id: int, authenticated: bool = Depends(verify_admin)):
    """切换项目的隐藏/显示状态"""
    with _file_lock:
        projects = read_json_file(PROJECTS_FILE, [], _locked=True)
        for p in projects:
            if p.get("id") == project_id:
                p["hidden"] = not p.get("hidden", False)
                _write_json_unlocked(PROJECTS_FILE, projects)
                return {"success": True, "hidden": p["hidden"], "message": "项目已隐藏" if p["hidden"] else "项目已显示"}
        raise HTTPException(status_code=404, detail=f"未找到 ID 为 {project_id} 的项目")


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, authenticated: bool = Depends(verify_admin)):
    """删除某个项目（需要管理员密码鉴权）"""
    with _file_lock:
        projects = read_json_file(PROJECTS_FILE, [], _locked=True)
        original_len = len(projects)
        projects = [p for p in projects if p.get("id") != project_id]
        if len(projects) == original_len:
            raise HTTPException(status_code=404, detail=f"未找到 ID 为 {project_id} 的项目")
        # 重新分配 ID，保持连续
        for i, p in enumerate(projects):
            p["id"] = i
        _write_json_unlocked(PROJECTS_FILE, projects)

    return {"success": True, "message": f"项目 ID {project_id} 已成功删除"}


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

    # 检查 Content-Type（可能为 None）
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="上传的文件类型错误，必须为图片格式")

    # image_type 长度限制（防止拒绝服务攻击）
    if len(image_type) > 50:
        raise HTTPException(status_code=400, detail="image_type 参数过长")

    # 解析 image_type: project1_extra → (project_idx=1, is_extra=True)
    is_extra = image_type.endswith("_extra")
    # 仅移除后缀 _extra（前6个字符），避免 replace 替换所有出现
    base_type = image_type[:-6] if is_extra else image_type

    filename = ""
    proj_idx = None  # 用于 projectN 类型
    assets_ref = ""  # 用于 projects.json 中的引用与回滚

    if base_type == "avatar":
        filename = "avatar.png"
    elif base_type == "hero_bg":
        filename = "hero_bg.png"
    elif re.match(r'^project\d+$', base_type):
        proj_idx = int(base_type.replace("project", ""))
        # 验证目标项目是否存在，并计算文件名 / 预更新 JSON
        with _file_lock:
            projects = read_json_file(PROJECTS_FILE, [], _locked=True)
            proj = next((p for p in projects if p.get("id") == proj_idx - 1), None)
            if not proj:
                raise HTTPException(status_code=404, detail=f"项目 ID {proj_idx - 1} 不存在")

            if is_extra:
                # 计算下一个序号（找最大序号+1，避免删除后覆盖）
                existing = proj.get("images", [])
                max_num = 0
                for img_path in existing:
                    match = re.search(rf"project{proj_idx}_(\d+)\.png$", img_path)
                    if match:
                        num = int(match.group(1))
                        if num > max_num:
                            max_num = num
                next_num = max_num + 1
                filename = f"project{proj_idx}_{next_num}.png"
                assets_ref = f"assets/{filename}"
                # 额外图片：先更新 JSON，文件写入失败时回滚（仅移除追加项，逻辑简单）
                if "images" not in proj:
                    proj["images"] = [f"assets/project{proj_idx}.png"]
                proj["images"].append(assets_ref)
                _write_json_unlocked(PROJECTS_FILE, projects)
            else:
                filename = f"{base_type}.png"
                assets_ref = f"assets/{filename}"
                # 主图：先不写 JSON，等文件保存成功后再更新 images[0]
    else:
        raise HTTPException(status_code=400, detail="未知的图片类型分类，无法保存")

    target_path = os.path.join(ASSETS_DIR, filename)

    # 保存文件
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        # 文件写入失败时，回滚 projectN_extra 在 JSON 中追加的引用
        if is_extra and assets_ref and proj_idx is not None:
            try:
                with _file_lock:
                    projects = read_json_file(PROJECTS_FILE, [], _locked=True)
                    proj = next((p for p in projects if p.get("id") == proj_idx - 1), None)
                    if proj and assets_ref in proj.get("images", []):
                        proj["images"].remove(assets_ref)
                        _write_json_unlocked(PROJECTS_FILE, projects)
            except Exception:
                pass  # 回滚失败也不应掩盖原始错误
        raise HTTPException(status_code=500, detail="保存图片文件失败，请稍后重试")

    # 主图：文件保存成功后，再更新 images[0]
    if not is_extra and re.match(r'^project\d+$', base_type):
        try:
            with _file_lock:
                projects = read_json_file(PROJECTS_FILE, [], _locked=True)
                proj = next((p for p in projects if p.get("id") == proj_idx - 1), None)
                if proj:
                    existing = proj.get("images", [])
                    if existing:
                        existing[0] = assets_ref
                    else:
                        proj["images"] = [assets_ref]
                    _write_json_unlocked(PROJECTS_FILE, projects)
        except Exception:
            # JSON 更新失败时，清理已写入的文件
            try:
                if os.path.exists(target_path):
                    os.remove(target_path)
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="保存图片信息失败，请稍后重试")

    return {"success": True, "message": f"图片已成功上传为 {filename}", "filename": filename}


@app.delete("/api/projects/{project_id}/images/{img_filename}")
async def delete_project_image(
    project_id: int,
    img_filename: str,
    authenticated: bool = Depends(verify_admin)
):
    """删除项目的某张额外图片"""
    # 路径穿越防护：只允许合法文件名
    if not img_filename or ".." in img_filename or "/" in img_filename or "\\" in img_filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    # 原子操作：读取-修改-写入在同一个锁内完成
    with _file_lock:
        projects = read_json_file(PROJECTS_FILE, [], _locked=True)
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
        _write_json_unlocked(PROJECTS_FILE, projects)
    return {"success": True, "message": f"已删除 {img_filename}"}


# ==========================================
# 6. 视频作品 API 路由 (Video Works)
# ==========================================
# 视频作品数据文件
VIDEO_WORKS_FILE = os.path.join(DATA_DIR, "video_works.json")

# 视频上传大小限制：100MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}


class VideoWorkSchema(BaseModel):
    """视频作品数据模型"""
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tech_stack: str = Field(default="", max_length=500)
    video_url: str = Field(default="", max_length=500)
    thumbnail_url: str = Field(default="", max_length=500)
    tags: List[str] = Field(default=[], max_length=20)


@app.get("/api/video-works")
def get_video_works():
    """获取所有视频作品"""
    return read_json_file(VIDEO_WORKS_FILE, [])


@app.post("/api/video-works")
def create_video_work(work: VideoWorkSchema, authenticated: bool = Depends(verify_admin)):
    """创建新视频作品"""
    with _file_lock:
        works = read_json_file(VIDEO_WORKS_FILE, [], _locked=True)
        new_id = len(works)
        new_work = {
            "id": new_id,
            "title": work.title,
            "description": work.description,
            "tech_stack": work.tech_stack,
            "video_url": work.video_url,
            "thumbnail_url": work.thumbnail_url,
            "tags": work.tags
        }
        works.append(new_work)
        _write_json_unlocked(VIDEO_WORKS_FILE, works)
    return {"success": True, "message": "视频作品创建成功", "id": new_id}


@app.post("/api/video-works/{work_id}")
def update_video_work(work_id: int, work: VideoWorkSchema, authenticated: bool = Depends(verify_admin)):
    """更新视频作品"""
    with _file_lock:
        works = read_json_file(VIDEO_WORKS_FILE, [], _locked=True)
        target_index = -1
        for i, w in enumerate(works):
            if w.get("id") == work_id:
                target_index = i
                break
        if target_index == -1:
            raise HTTPException(status_code=404, detail="未找到该视频作品")
        
        works[target_index] = {
            "id": work_id,
            "title": work.title,
            "description": work.description,
            "tech_stack": work.tech_stack,
            "video_url": works[target_index].get("video_url", ""),
            "thumbnail_url": works[target_index].get("thumbnail_url", ""),
            "tags": work.tags
        }
        _write_json_unlocked(VIDEO_WORKS_FILE, works)
    return {"success": True, "message": "视频作品更新成功"}


@app.delete("/api/video-works/{work_id}")
def delete_video_work(work_id: int, authenticated: bool = Depends(verify_admin)):
    """删除视频作品（同时清理关联的视频和封面文件）"""
    with _file_lock:
        works = read_json_file(VIDEO_WORKS_FILE, [], _locked=True)
        target = next((w for w in works if w.get("id") == work_id), None)
        if target:
            # 删除关联的视频和封面文件
            for url_key in ("video_url", "thumbnail_url"):
                url = target.get(url_key, "")
                if url:
                    safe_name = os.path.basename(url)
                    fpath = os.path.join(ASSETS_DIR, safe_name)
                    if os.path.exists(fpath) and os.path.realpath(fpath).startswith(os.path.realpath(ASSETS_DIR)):
                        os.remove(fpath)
        works = [w for w in works if w.get("id") != work_id]
        for i, w in enumerate(works):
            w["id"] = i
        _write_json_unlocked(VIDEO_WORKS_FILE, works)
    return {"success": True, "message": "视频作品已删除"}


@app.post("/api/video-works/{work_id}/upload-video")
async def upload_video(
    work_id: int,
    file: UploadFile = File(...),
    authenticated: bool = Depends(verify_admin)
):
    """上传视频文件"""
    # 先验证作品是否存在
    with _file_lock:
        works = read_json_file(VIDEO_WORKS_FILE, [], _locked=True)
        work = next((w for w in works if w["id"] == work_id), None)
    if not work:
        raise HTTPException(status_code=404, detail="未找到该视频作品")

    # 文件大小校验
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=400, detail=f"文件过大，最大允许 {MAX_VIDEO_SIZE // 1024 // 1024}MB")

    # 文件扩展名校验
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的视频格式，仅允许：{', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}")

    # 删除旧视频文件
    old_url = work.get("video_url", "")
    if old_url:
        old_name = os.path.basename(old_url)
        old_path = os.path.join(ASSETS_DIR, old_name)
        if os.path.exists(old_path) and os.path.realpath(old_path).startswith(os.path.realpath(ASSETS_DIR)):
            os.remove(old_path)

    filename = f"video_{work_id}{ext}"
    target_path = os.path.join(ASSETS_DIR, filename)

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        with _file_lock:
            works = read_json_file(VIDEO_WORKS_FILE, [], _locked=True)
            w = next((w for w in works if w["id"] == work_id), None)
            if w:
                w["video_url"] = f"assets/{filename}"
                _write_json_unlocked(VIDEO_WORKS_FILE, works)

        return {"success": True, "message": "视频上传成功", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail="视频上传失败")


@app.post("/api/video-works/{work_id}/upload-thumbnail")
async def upload_thumbnail(
    work_id: int,
    file: UploadFile = File(...),
    authenticated: bool = Depends(verify_admin)
):
    """上传视频封面图"""
    # 先验证作品是否存在
    with _file_lock:
        works = read_json_file(VIDEO_WORKS_FILE, [], _locked=True)
        work = next((w for w in works if w["id"] == work_id), None)
    if not work:
        raise HTTPException(status_code=404, detail="未找到该视频作品")

    # 文件大小校验
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"文件过大，最大允许 {MAX_UPLOAD_SIZE // 1024 // 1024}MB")

    # 文件扩展名校验
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的图片格式，仅允许：{', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # 删除旧封面文件
    old_url = work.get("thumbnail_url", "")
    if old_url:
        old_name = os.path.basename(old_url)
        old_path = os.path.join(ASSETS_DIR, old_name)
        if os.path.exists(old_path) and os.path.realpath(old_path).startswith(os.path.realpath(ASSETS_DIR)):
            os.remove(old_path)

    filename = f"video_{work_id}_thumb{ext}"
    target_path = os.path.join(ASSETS_DIR, filename)

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        with _file_lock:
            works = read_json_file(VIDEO_WORKS_FILE, [], _locked=True)
            w = next((w for w in works if w["id"] == work_id), None)
            if w:
                w["thumbnail_url"] = f"assets/{filename}"
                _write_json_unlocked(VIDEO_WORKS_FILE, works)

        return {"success": True, "message": "封面上传成功", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail="封面上传失败")


# ==========================================
# 6.5 技能管理 API 路由 (Skills Management)
# ==========================================
SKILLS_FILE = os.path.join(DATA_DIR, "skills.json")


class SkillSchema(BaseModel):
    """技能数据模型"""
    title: str = Field(..., min_length=1, max_length=100)
    icon: str = Field(default="code", max_length=50)
    description: str = Field(default="", max_length=500)
    proficiency: int = Field(default=80, ge=0, le=100)
    hidden: bool = Field(default=False)


@app.get("/api/skills")
def get_skills():
    """获取所有未隐藏的技能（前端公开接口，按 hidden 过滤并重新编号显示顺序）"""
    all_skills = read_json_file(SKILLS_FILE, [])
    visible = [s for s in all_skills if not s.get("hidden", False)]
    # 重新编号 id / order（从 0 开始连续，保证前端顺序与动画正常）
    for i, s in enumerate(visible):
        s["id"] = i
        s["order"] = i
    return visible


@app.get("/api/admin/skills")
def get_admin_skills(authenticated: bool = Depends(verify_admin)):
    """获取所有技能包括已隐藏的（管理后台接口）"""
    return read_json_file(SKILLS_FILE, [])


@app.post("/api/skills")
def create_skill(skill: SkillSchema, authenticated: bool = Depends(verify_admin)):
    """创建新技能"""
    with _file_lock:
        skills = read_json_file(SKILLS_FILE, [], _locked=True)
        new_id = len(skills)
        new_skill = {
            "id": new_id,
            "title": skill.title,
            "icon": skill.icon,
            "description": skill.description,
            "proficiency": skill.proficiency,
            "hidden": skill.hidden,
            "order": new_id
        }
        skills.append(new_skill)
        _write_json_unlocked(SKILLS_FILE, skills)
    return {"success": True, "message": "技能创建成功", "id": new_id}


@app.post("/api/skills/reorder")
def reorder_skills(order: List[int], authenticated: bool = Depends(verify_admin)):
    """重排技能顺序"""
    with _file_lock:
        skills = read_json_file(SKILLS_FILE, [], _locked=True)
        existing_ids = {s.get("id") for s in skills}
        order_ids = set(order)
        # 校验：排序列表必须包含所有现有技能，不能丢弃也不能凭空添加
        if existing_ids != order_ids:
            raise HTTPException(status_code=400, detail="排序列表必须包含所有技能的 ID，不能多也不能少")
        reordered = []
        for skill_id in order:
            for s in skills:
                if s.get("id") == skill_id:
                    reordered.append(s)
                    break
        for i, s in enumerate(reordered):
            s["id"] = i
            s["order"] = i
        _write_json_unlocked(SKILLS_FILE, reordered)
    return {"success": True, "message": "技能排序已更新"}


@app.post("/api/skills/{skill_id}/toggle-hidden")
def toggle_skill_hidden(skill_id: int, authenticated: bool = Depends(verify_admin)):
    """切换技能的隐藏/显示状态"""
    with _file_lock:
        skills = read_json_file(SKILLS_FILE, [], _locked=True)
        for s in skills:
            if s.get("id") == skill_id:
                s["hidden"] = not s.get("hidden", False)
                _write_json_unlocked(SKILLS_FILE, skills)
                return {"success": True, "hidden": s["hidden"], "message": "技能已隐藏" if s["hidden"] else "技能已显示"}
        raise HTTPException(status_code=404, detail="未找到该技能")


@app.post("/api/skills/{skill_id}")
def update_skill(skill_id: int, skill: SkillSchema, authenticated: bool = Depends(verify_admin)):
    """更新技能"""
    with _file_lock:
        skills = read_json_file(SKILLS_FILE, [], _locked=True)
        target_index = -1
        for i, s in enumerate(skills):
            if s.get("id") == skill_id:
                target_index = i
                break
        if target_index == -1:
            raise HTTPException(status_code=404, detail="未找到该技能")

        skills[target_index] = {
            "id": skill_id,
            "title": skill.title,
            "icon": skill.icon,
            "description": skill.description,
            "proficiency": skill.proficiency,
            "hidden": skill.hidden,
            "order": skills[target_index].get("order", target_index)
        }
        _write_json_unlocked(SKILLS_FILE, skills)
    return {"success": True, "message": "技能更新成功"}


@app.delete("/api/skills/{skill_id}")
def delete_skill(skill_id: int, authenticated: bool = Depends(verify_admin)):
    """删除技能"""
    with _file_lock:
        skills = read_json_file(SKILLS_FILE, [], _locked=True)
        skills = [s for s in skills if s.get("id") != skill_id]
        for i, s in enumerate(skills):
            s["id"] = i
            s["order"] = i
        _write_json_unlocked(SKILLS_FILE, skills)
    return {"success": True, "message": "技能已删除"}


# ==========================================
# 7. 留言 API 路由 (Messages Management)
# ==========================================
# 留言限流：每 IP 每小时最多 5 条
_message_rate_limit_store: Dict[str, list] = defaultdict(list)
_MESSAGE_RATE_LIMIT_MAX = 5
_MESSAGE_RATE_LIMIT_WINDOW = 3600  # 1 小时
_last_message_cleanup: float = _time.time()
_MESSAGE_CLEANUP_INTERVAL = 3600  # 每 1 小时清理一次过期条目


def _cleanup_message_rate_limit_store():
    """定期清理过期的留言限流记录，防止内存泄漏"""
    global _last_message_cleanup
    now = _time.time()
    if now - _last_message_cleanup < _MESSAGE_CLEANUP_INTERVAL:
        return
    _last_message_cleanup = now
    expired_keys = [k for k, v in _message_rate_limit_store.items() 
                    if not any(now - t < _MESSAGE_RATE_LIMIT_WINDOW for t in v)]
    for k in expired_keys:
        del _message_rate_limit_store[k]


@app.post("/api/messages")
def create_message(message_data: MessageCreateSchema, request: Request):
    """用户提交联系留言意向，写入本地 JSON（带限流保护）"""
    # 定期清理过期限流记录
    _cleanup_message_rate_limit_store()
    
    # 限流检查
    client_ip = _get_client_ip(request)
    now = _time.time()
    msg_requests = _message_rate_limit_store.get(f"msg:{client_ip}", [])
    _message_rate_limit_store[f"msg:{client_ip}"] = [t for t in msg_requests if now - t < _MESSAGE_RATE_LIMIT_WINDOW]
    if len(_message_rate_limit_store[f"msg:{client_ip}"]) >= _MESSAGE_RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="留言提交过于频繁，请 1 小时后再试")
    _message_rate_limit_store[f"msg:{client_ip}"].append(now)

    # 原子操作：读取-修改-写入在同一个锁内完成，防止并发导致ID重复
    with _file_lock:
        messages = read_json_file(MESSAGES_FILE, [], _locked=True)
        
        # 构建留言对象，补充提交时间
        # 使用最大 ID + 1 避免删除留言后 ID 重复
        max_id = max([m.get("id", 0) for m in messages], default=0)
        new_message = {
            "id": max_id + 1,
            "name": message_data.name,
            "email": message_data.email,
            "project_type": message_data.project_type,
            "budget": message_data.budget,
            "message": message_data.message,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        messages.append(new_message)
        _write_json_unlocked(MESSAGES_FILE, messages)
    
    return {"success": True, "message": "留言意向已成功发送，感谢您的联系！"}


@app.get("/api/messages")
def get_messages(authenticated: bool = Depends(verify_admin)):
    """管理员获取所有收到的客户留言（需要管理员密码鉴权）"""
    messages = read_json_file(MESSAGES_FILE, [])
    # 按时间降序排列，最新提交的排在最前
    return list(reversed(messages))


TESTIMONIALS_FILE = os.path.join(DATA_DIR, "testimonials.json")


class TestimonialsSchema(BaseModel):
    enabled: bool = False
    items: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator('items')
    @classmethod
    def validate_items(cls, v):
        if len(v) > 20:
            raise ValueError('评价条目不能超过 20 条')
        for item in v:
            if 'name' in item and len(str(item['name'])) > 100:
                raise ValueError('评价人姓名过长')
            if 'content' in item and len(str(item['content'])) > 1000:
                raise ValueError('评价内容过长')
            if 'role' in item and len(str(item['role'])) > 100:
                raise ValueError('评价人职位过长')
            if 'company' in item and len(str(item['company'])) > 100:
                raise ValueError('评价人公司过长')
            if 'avatar' in item and len(str(item['avatar'])) > 500:
                raise ValueError('评价人头像URL过长')
        return v


@app.get("/api/testimonials")
def get_testimonials():
    """获取客户评价配置（公开接口，前端根据 enabled 决定是否显示）"""
    return read_json_file(TESTIMONIALS_FILE, {"enabled": False, "items": []})


@app.post("/api/testimonials")
def update_testimonials(
    payload: TestimonialsSchema,
    authenticated: bool = Depends(verify_admin)
):
    """更新客户评价配置（需要管理员密码鉴权）"""
    write_json_file(TESTIMONIALS_FILE, payload.model_dump())
    return {"success": True, "message": "客户评价配置已更新"}


# ==========================================
# 6. 基本信息 API 路由 (Profile Management)
# ==========================================
PROFILE_FILE = os.path.join(DATA_DIR, "profile.json")


class HeroStatItem(BaseModel):
    value: str = Field("", max_length=20)
    suffix: str = Field("", max_length=10)
    label: str = Field("", max_length=50)
    show: bool = Field(default=True)


class HeroButton(BaseModel):
    text: str = Field("", max_length=50)
    link: str = Field("", max_length=500)
    show: bool = Field(default=True)


class HeroConfig(BaseModel):
    showStats: bool = Field(default=True)
    showTyping: bool = Field(default=True)
    typingTexts: List[str] = Field(default_factory=lambda: ["AI 产品经理", "独立开发者", "Agent 工程化实践者"])
    stats: List[HeroStatItem] = Field(default_factory=list)
    primaryButton: HeroButton = Field(default_factory=lambda: HeroButton(text="查看作品集", link="#portfolio", show=True))
    secondaryButton: HeroButton = Field(default_factory=lambda: HeroButton(text="下载简历", link="#contact", show=True))


class ProfileSchema(BaseModel):
    email: str = Field("", max_length=200)
    wechat: str = Field("", max_length=100)
    wechatNote: str = Field("", max_length=200)
    status: str = Field("", max_length=100)
    statusEn: str = Field("", max_length=100)
    socials: List[Dict[str, Any]] = Field(default_factory=list)
    hero: HeroConfig = Field(default_factory=HeroConfig)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError('邮箱格式不正确')
        return v

    @field_validator('socials')
    @classmethod
    def validate_socials(cls, v):
        if len(v) > 10:
            raise ValueError('社交链接不能超过 10 个')
        for item in v:
            if 'url' in item and len(str(item['url'])) > 500:
                raise ValueError('社交链接 URL 过长')
            if 'label' in item and len(str(item['label'])) > 50:
                raise ValueError('社交链接标签过长')
            if 'icon' in item and len(str(item['icon'])) > 50:
                raise ValueError('社交链接图标名称过长')
        return v


@app.get("/api/profile")
def get_profile():
    """获取基本信息（公开接口，前端展示用）"""
    return read_json_file(PROFILE_FILE, {})


@app.post("/api/profile")
def update_profile(
    payload: ProfileSchema,
    authenticated: bool = Depends(verify_admin)
):
    """更新基本信息（需要管理员密码鉴权）"""
    data = {
        "email": payload.email,
        "wechat": payload.wechat,
        "wechatNote": payload.wechatNote,
        "status": payload.status,
        "statusEn": payload.statusEn,
        "socials": payload.socials,
        "hero": payload.hero.model_dump()
    }
    write_json_file(PROFILE_FILE, data)
    return {"success": True, "message": "基本信息已更新"}


@app.post("/api/admin/resume")
async def upload_resume(
    file: UploadFile = File(...),
    authenticated: bool = Depends(verify_admin)
):
    """上传简历 PDF（需要管理员密码鉴权）"""
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    max_resume_size = 10 * 1024 * 1024
    if file_size > max_resume_size:
        raise HTTPException(status_code=400, detail="简历文件过大，最大允许 10MB")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="仅支持 PDF 格式简历")

    if not file.content_type or "pdf" not in file.content_type.lower():
        raise HTTPException(status_code=400, detail="上传的文件类型错误，必须为 PDF")

    target_path = os.path.join(ASSETS_DIR, "resume.pdf")
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存简历失败：{str(e)}")

    return {"success": True, "message": "简历上传成功", "url": "assets/resume.pdf"}


# ==========================================
# 7. 辅助路由 (Health / robots.txt / sitemap / 404)
# ==========================================


@app.get("/health")
def health_check():
    """健康检查接口（监控用）"""
    return {"status": "ok", "version": "2.0.0"}


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
    """自定义 404 页面：根据 Accept 头返回 HTML 或 JSON"""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return Response(
            status_code=404,
            media_type="text/html",
            content="""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>404 页面未找到</title></head>
<body style="font-family:sans-serif;text-align:center;padding-top:80px;color:#334155;">
    <h1 style="font-size:3rem;color:#6366f1;">404</h1>
    <p>页面未找到，请求的资源不存在。</p>
    <p><a href="/" style="color:#6366f1;">返回首页</a></p>
</body>
</html>"""
        )
    return JSONResponse(
        status_code=404,
        content={"detail": "页面未找到", "message": "请求的资源不存在"}
    )
