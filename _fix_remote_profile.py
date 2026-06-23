import json
import paramiko

HOST = "121.41.169.43"
USER = "root"
PASSWORD = "Jyy920220!"
REMOTE_PATH = "/root/jiayuyuan/data/profile.json"

local_profile = {
    "email": "776706958@qq.com",
    "wechat": "libaweiyu",
    "wechatNote": "请备注合作意向",
    "status": "接受委托中",
    "statusEn": "Available",
    "socials": [
        {
            "icon": "github",
            "label": "GitHub",
            "url": "https://github.com/Caser-86"
        }
    ],
    "hero": {
        "showStats": True,
        "showTyping": True,
        "typingTexts": ["AI 产品经理", "独立开发者", "Agent 工程化实践者"],
        "stats": [
            {"value": "3", "suffix": "+", "label": "年产品经验", "show": True},
            {"value": "12", "suffix": "+", "label": "完整项目", "show": True},
            {"value": "6", "suffix": "", "label": "开源工具", "show": True}
        ],
        "primaryButton": {"text": "查看作品集", "link": "#portfolio", "show": True},
        "secondaryButton": {"text": "下载简历", "link": "#contact", "show": True}
    }
}

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASSWORD)

try:
    sftp = client.open_sftp()
    try:
        with sftp.file(REMOTE_PATH, "r") as f:
            remote_text = f.read().decode("utf-8")
        remote_profile = json.loads(remote_text)
    except FileNotFoundError:
        remote_profile = {}

    # 合并：保留服务器上的字段，补充本地新增的字段
    merged = {**local_profile, **remote_profile}
    if "hero" in remote_profile and "hero" in local_profile:
        merged["hero"] = {**local_profile["hero"], **remote_profile["hero"]}

    merged_text = json.dumps(merged, ensure_ascii=False, indent=2)
    with sftp.file(REMOTE_PATH, "w") as f:
        f.write(merged_text)
    print("profile.json 已修复")
finally:
    client.close()
