import paramiko, os

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('121.41.169.43', username='root', key_filename=r'C:\Users\Administrator\.ssh\id_ed25519', timeout=10)

sftp = client.open_sftp()

files_to_upload = [
    (r'd:\大模型学习\个人网站\main.py', '/root/jiayuyuan/main.py'),
    (r'd:\大模型学习\个人网站\admin.html', '/root/jiayuyuan/admin.html'),
    (r'd:\大模型学习\个人网站\index.html', '/root/jiayuyuan/index.html'),
    (r'd:\大模型学习\个人网站\data\video_works.json', '/root/jiayuyuan/data/video_works.json'),
    (r'd:\大模型学习\个人网站\assets\video_0.mp4', '/root/jiayuyuan/assets/video_0.mp4'),
    (r'd:\大模型学习\个人网站\assets\video_0_thumb.jpg', '/root/jiayuyuan/assets/video_0_thumb.jpg'),
]

for local, remote in files_to_upload:
    if os.path.exists(local):
        sftp.put(local, remote)
        print(f'uploaded: {os.path.basename(local)}')
    else:
        print(f'skipped (not found): {local}')

sftp.close()

cmd = 'cd /root/jiayuyuan && git config user.email "admin@libaweiyu.xyz" && git config user.name "admin" && git add -A && git commit -m "feat: add video work hidden toggle; fix project/video click interaction" && systemctl restart jiayuyuan && sleep 1 && systemctl is-active jiayuyuan'
stdin, stdout, stderr = client.exec_command(cmd)
print('OUT:', stdout.read().decode())
print('ERR:', stderr.read().decode())
client.close()
