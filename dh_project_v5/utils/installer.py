# -*- coding: utf-8 -*-
import subprocess
import sys
from pathlib import Path
import pkg_resources  # 패키지 확인용

def install_requirements():
    """requirements.txt 에 있는 패키지를 확인 후 없으면 설치"""
    print("Python3.9 기준으로 제작되었습니다.")
    try:
        base_dir = Path(__file__).resolve().parent   # 일반 실행
    except NameError:
        base_dir = Path.cwd()                        # Jupyter 실행

    req_file = base_dir / "requirements.txt"
    if not req_file.exists():
        print("[오류] requirements.txt 파일이 없습니다.")
        return

    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            package = line.strip()
            if not package or package.startswith("#"):
                continue

            pkg_name = package.split("==")[0]  # 버전 제외 이름만
            try:
                pkg_resources.get_distribution(pkg_name)
                print(f"[확인 완료] {package} 이미 설치됨 ✅")
            except pkg_resources.DistributionNotFound:
                print(f"[설치 필요] {package} 라이브러리가 없습니다. 설치를 진행합니다...")
                subprocess.check_check_call([sys.executable, "-m", "pip", "install", package])
