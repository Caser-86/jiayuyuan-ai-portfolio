from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def requirement_lines(path: str):
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            yield stripped


def test_cdn_scripts_are_version_pinned_and_integrity_checked():
    for html_file in ("index.html", "admin.html"):
        html = read_text(html_file)

        assert "@latest" not in html
        for line in html.splitlines():
            if '<script src="https://' in line:
                assert "integrity=" in line
                assert "crossorigin=" in line


def test_python_requirements_are_exactly_pinned():
    for req_file in ("requirements.txt", "requirements-dev.txt"):
        for line in requirement_lines(req_file):
            assert "==" in line
            assert ">=" not in line
            assert "<=" not in line
            assert "~=" not in line


def test_deploy_scripts_do_not_install_unpinned_packages():
    deploy_script = read_text("deploy-aliyun.sh")

    assert "pip install -i https://mirrors.aliyun.com/pypi/simple/ gunicorn" not in deploy_script
