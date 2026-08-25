# Infrastructure

Docker 실행 설정은 저장소 루트의 compose.yaml과 compose.prod.yaml에서 관리합니다.

- 개발: docker compose up --build
- 프로덕션 이미지 확인: docker compose -f compose.yaml -f compose.prod.yaml up --build -d

클라우드별 배포 설정이 추가될 때 이 디렉터리에 둡니다.

