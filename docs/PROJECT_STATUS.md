# Pivot_Fixer 개발 현황

확인일 2026-11-24 · 기본 브랜치 `main` · [개발 브랜치](https://github.com/rodetoast/Pivot-Fixer/tree/codex/migration-checkpoint-20261117) · [조사 기준 소스 커밋](https://github.com/rodetoast/Pivot-Fixer/commit/8f02d60e98c609415821dd221a4611f2aa762807)

픽셀 아티스트가 PNG의 피벗과 여백을 맞추고 Aseprite 레이어를 보정합니다.

- 제품 표시명 **Pivot_Fixer** · 런처 app_id `pivot-fixer`
- 기술 구성 Python, Tkinter, Pillow, tkinterdnd2, PyInstaller
- 구현 기능 피벗과 캔버스 일괄 보정, Aseprite 레이어 이동 및 보정 복사본

## 배포 상태

**0.3.3** · `0.3.3-team-80b84c9` · `pivot-fixer--0.3.3-team-80b84c9.zip` (onedir) · 실행 파일 `Pivot_Fixer_v0.3.3/Pivot_Fixer_v0.3.3.exe`. [Rod 운영 카탈로그](https://github.com/rodetoast/creative-group-releases/releases/tag/rodetoast-catalog-000015)

소스 저장소의 독립 Latest Release는 확인되지 않았습니다.

## 개발과 검증

0.3.3 운영 및 선별 개발 체크포인트를 확인했습니다. 후속 바이너리는 미확인입니다.

**알려진 제약과 미검증** 여러 로컬 개발 사본의 변경을 병합하지 않았습니다. 새 실기동 검증은 없습니다.

이번 확인에서는 원격 Git과 공개 서명 카탈로그를 대조했습니다. 기능 시험과 패키징은 기존 보고서의 범위를 따릅니다.

## 패키징과 다음 단계

run.bat 실행과 Pivot_Fixer.spec 빌드를 따릅니다. 운영 배포는 폴더형입니다. [공통 배포 절차](https://github.com/rodetoast/southpaw-development-hub/blob/main/docs/RELEASE_GUIDE.md)

**다음 단계** 다음 작업에서 선택한 작업 사본의 HEAD와 원격 차이를 확인합니다.

[README.md](https://github.com/rodetoast/Pivot-Fixer/blob/8f02d60e98c609415821dd221a4611f2aa762807/README.md) · [run.bat](https://github.com/rodetoast/Pivot-Fixer/blob/8f02d60e98c609415821dd221a4611f2aa762807/run.bat) · [Pivot_Fixer.spec](https://github.com/rodetoast/Pivot-Fixer/blob/8f02d60e98c609415821dd221a4611f2aa762807/Pivot_Fixer.spec) · [개발 허브 요약](https://github.com/rodetoast/southpaw-development-hub/blob/main/projects/pivot-fixer.md)
