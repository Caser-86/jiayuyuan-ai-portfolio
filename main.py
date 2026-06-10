# -*- coding: utf-8 -*-
import os
import json
import shutil
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders
from pydantic import BaseModel

app = FastAPI(
    title="贾玉元个人主页后端管理系统",
    description="基于 FastAPI 构建，提供项目数据读取与修改、图像文件上传和留言板管理功能。",
    version="0.1.0",
)

# 允许所有来源跨域（开发期）。生产可改成 ["https://libaweiyu.xyz"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 给 HTML 页面和上传图片加 no-cache 头（防止浏览器缓存导致改了上传的图片看不到效果）
@app.middleware("http")
async def no_cache_html(request, call_next):
    response = await call_next(request)
    path = request.url.path
    # HTML 页面、admin.html、index.html 强制不缓存
    if path.endswith(".html") or path in ("/", "/admin"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    # 上传的图片资产（项目图、头像、背景、二维码）也不缓存
    elif path.startswith("/assets/") and any(path.endswith(suffix) for suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
        # 检查是否是 admin 可上传的图片（project1-6, avatar, hero_bg, wechat_qr）
        fname = path.split("/")[-1].lower()
        if any(fname.startswith(prefix) for prefix in ("project", "avatar", "hero_bg", "wechat_qr")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    return response

# 基础文件目录路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
MESSAGES_FILE = os.path.join(DATA_DIR, "messages.json")
PROFILE_FILE = os.path.join(DATA_DIR, "profile.json")
TESTIMONIALS_FILE = os.path.join(DATA_DIR, "testimonials.json")

# 管理后台默认访问密码
ADMIN_PASSWORD = "admin123"

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
    """向指定路径写入 JSON 数据"""
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
# 使用自定义 NoCacheStaticFiles，对可上传的图片（项目图、头像、背景、二维码）加 no-cache 头
class NoCacheStaticFiles(StaticFiles):
    """对特定文件名前缀的图片强制 no-cache，避免浏览器缓存导致上传后看不到效果"""
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await super().__call__(scope, receive, send)
        # 在 send http.response.start 消息里追加 Cache-Control 头
        async def custom_send(message):
            if message["type"] == "http.response.start":
                path = scope.get("path", "").lower()
                fname = path.split("/")[-1]
                # 项目图 / 头像 / 背景 / 二维码 → no-cache
                if any(fname.startswith(pre) for pre in ("project", "avatar", "hero_bg", "wechat_qr")):
                    headers = MutableHeaders(scope=message)
                    headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                    headers["Pragma"] = "no-cache"
                    headers["Expires"] = "0"
            await send(message)
        return await super().__call__(scope, receive, custom_send)

app.mount("/assets", NoCacheStaticFiles(directory=ASSETS_DIR), name="assets")


# ==========================================
# 2. 鉴权 API 路由
# ==========================================
@app.post("/api/admin/login")
def admin_login(payload: dict):
    """后台登录验证接口"""
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
        
    # 保留原项目的图片和 ID，仅更新表单提交字段
    updated_project = {
        "id": project_id,
        "title": project_data.title,
        "tags": project_data.tags,
        "client": project_data.client,
        "duration": project_data.duration,
        "tech": project_data.tech,
        "img": projects[target_index].get("img", f"assets/project{project_id + 1}.png"),
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
    根据 image_type 的值 (avatar, hero_bg, project1 ~ project6) 将图片覆盖保存。
    为了兼容 index.html 原先的图片路径，我们将统一将文件保存为对应的 png 格式。
    """
    # 验证上传文件类型是否为图片
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="上传的文件类型错误，必须为图片格式")
        
    filename = ""
    if image_type == "avatar":
        filename = "avatar.png"
    elif image_type == "hero_bg":
        filename = "hero_bg.png"
    elif image_type == "wechat_qr":
        filename = "wechat_qr.png"
    elif image_type in [f"project{i}" for i in range(1, 7)]:
        filename = f"{image_type}.png"
    else:
        raise HTTPException(status_code=400, detail="未知的图片类型分类，无法保存")
        
    target_path = os.path.join(ASSETS_DIR, filename)
    
    try:
        # 保存图片，直接覆盖旧文件
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"success": True, "message": f"图片已成功上传并覆盖为 {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存图片文件失败: {str(e)}")


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


# ==========================================
# 6. 站点基本信息 API (Profile)
# ==========================================
@app.get("/api/profile")
def get_profile():
    """公开接口：获取首页"关于合作"区块的邮箱、微信、合作状态、社交媒体链接"""
    return read_json_file(PROFILE_FILE, {})


@app.post("/api/profile")
def update_profile(profile_data: dict, authenticated: bool = Depends(verify_admin)):
    """管理员更新站点基本信息（需要管理员密码鉴权）"""
    # 允许更新的字段白名单
    allowed_fields = {
        "email", "wechat", "wechatNote", "wechatQr",
        "status", "statusEn",
        "socials"
    }
    current = read_json_file(PROFILE_FILE, {})
    for key, value in profile_data.items():
        if key in allowed_fields:
            current[key] = value
    write_json_file(PROFILE_FILE, current)
    return {"success": True, "message": "站点基本信息已成功更新"}


# ==========================================
# 5. 客户评价 API 路由 (Testimonials)
# ==========================================
@app.get("/api/testimonials")
def get_testimonials():
    """公开接口：获取客户评价。enabled=false 时不展示，items 留给以后填写真实评价"""
    return read_json_file(TESTIMONIALS_FILE, {"enabled": False, "items": []})


@app.post("/api/testimonials")
def update_testimonials(payload: dict, authenticated: bool = Depends(verify_admin)):
    """管理员更新客户评价（需要管理员密码鉴权）"""
    current = read_json_file(TESTIMONIALS_FILE, {"enabled": False, "items": []})
    if "enabled" in payload:
        current["enabled"] = bool(payload["enabled"])
    if "items" in payload and isinstance(payload["items"], list):
        current["items"] = payload["items"]
    write_json_file(TESTIMONIALS_FILE, current)
    return {"success": True, "message": "客户评价已更新"}
