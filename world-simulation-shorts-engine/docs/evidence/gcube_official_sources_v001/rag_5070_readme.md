# rag-mcp-stack

Open WebUI + Ollama + Qdrant + MCP 기반 RAG 챗봇 및 파일 에이전트 스택입니다.
gcube 플랫폼에 4개 컨테이너를 단일 워크로드로 배포합니다.

---

## 이미지 목록

| 이미지 | 베이스 | 포트 | 역할 |
|---|---|---|---|
| `ghcr.io/chaeyoon-08/rag-webui:latest` | open-webui `v0.8.6` | 8080 | 사용자 UI (Open WebUI) |
| `ghcr.io/chaeyoon-08/rag-ollama:latest` | ollama `v0.20.2` | 11434 | LLM 및 임베딩 추론 서버 |
| `ghcr.io/chaeyoon-08/rag-qdrant:latest` | qdrant `v1.17.0` | 6333 | 벡터 데이터베이스 (스냅샷 자동 저장/복원) |
| `ghcr.io/chaeyoon-08/rag-mcp:latest` | python `3.11-slim` | 8000 | MCP 파일시스템 에이전트 |

> 같은 워크로드 내 컨테이너는 `localhost`로 상호 통신합니다. 별도 네트워크 설정은 필요하지 않습니다.

---

## 컨테이너 상호작용

```
사용자
  │
  ▼
rag-webui (8080)
  │
  ├─── LLM 추론 / 임베딩 ──────► rag-ollama (11434)
  │                                    │
  │                               qwen3-embedding:8b (임베딩)
  │                               qwen3:8b/14b (채팅)
  │
  ├─── 벡터 검색 / 저장 ──────► rag-qdrant (6333)
  │                                    │
  │                               문서 임베딩 벡터 저장
  │                               RAG 검색 쿼리 처리
  │
  └─── 파일시스템 도구 ────────► rag-mcp (8000)
                                       │
                                  /mcp_data 읽기/쓰기
                                  (MCP over HTTP)
```

**RAG 파이프라인 흐름:**
1. 사용자가 문서를 업로드 → rag-webui가 수신
2. rag-webui가 rag-ollama(`qwen3-embedding:8b`)에 임베딩 요청
3. 임베딩 벡터를 rag-qdrant에 저장
4. 채팅 시 질문을 임베딩 → rag-qdrant에서 유사 청크 검색
5. 검색된 컨텍스트 + 질문을 rag-ollama(LLM)에 전달 → 응답 생성

**MCP 파이프라인 흐름:**
1. 사용자가 채팅에서 Files_Agent 도구 활성화
2. rag-webui가 rag-mcp(`http://localhost:8000`)에 도구 호출
3. rag-mcp가 `/mcp_data`(Dropbox 마운트) 경로의 파일 조회/읽기/쓰기 수행
4. 결과를 LLM 컨텍스트로 반환

---

## 저장소 구조

```
├── webui/
│   ├── Dockerfile          한국어 로케일, Tesseract OCR, 기본 환경변수 내장
│   ├── entrypoint.sh       시작 시 DB 복원 → 10분 주기 DB 백업 → 서버 실행
│   └── patch_files.py      FUSE SQLite db.refresh() 실패 패치 (빌드 시 적용)
├── ollama/
│   ├── Dockerfile          OLLAMA_MODELS 기본값 내장 (qwen3:8b, qwen3-embedding:8b)
│   └── pull_models.sh      서버 기동 후 OLLAMA_MODELS 목록을 순서대로 pull
├── qdrant/
│   ├── Dockerfile          qdrant v1.17.0 베이스, curl 설치, snapshot.sh 내장
│   └── snapshot.sh         시작 시 스냅샷 복원 → 10분 주기 스냅샷 저장
├── mcp/
│   ├── Dockerfile          Node.js 22 + mcpo 설치, config.json 내장
│   ├── entrypoint.sh       mcpo 서버 기동
│   └── config.json         /mcp_data 경로를 MCP 파일시스템 도구로 노출
├── docs/                   배포 튜토리얼, 테스트 문서 (git 미추적)
└── .github/workflows/
    ├── build-webui.yml     webui/ 변경 시 GHCR 자동 빌드
    ├── build-ollama.yml    ollama/ 변경 시 GHCR 자동 빌드
    ├── build-qdrant.yml    qdrant/ 변경 시 GHCR 자동 빌드
    └── build-mcp.yml       mcp/ 변경 시 GHCR 자동 빌드
```

---

## 목적 스펙

| 항목 | 값 |
|---|---|
| GPU | RTX 5070 Ti 이상 (VRAM 16GB 이상) |
| 최소 CUDA | 12.8.0 (Blackwell sm_120 완전 지원) |
| 공유 메모리 | 8GB |

> 기본 모델(qwen3:8b + qwen3-embedding:8b) 동시 로드 시 약 9.5GB 사용.
> RTX 5090(32GB)에서는 `OLLAMA_MODELS=qwen3:14b,qwen3-embedding:8b`로 업그레이드 가능합니다.

---

## 주요 설계 결정

### gcube FUSE 저장소 제약

gcube의 영속 저장소(Dropbox, S3)는 모두 FUSE 기반입니다. FUSE는 SQLite가 필요로 하는 파일 락을 지원하지 않아 DB를 직접 마운트하면 손상됩니다. 이를 우회하기 위해 DB는 컨테이너 로컬 디스크에 두고, 백업 파일만 Dropbox에 저장합니다.

### Open WebUI DB 백업 기반 영속성

- `/app/backend/data`(DB)는 컨테이너 **로컬 디스크** 유지 (마운트 없음)
- 10분 주기로 Python `sqlite3.backup()` API로 `/db_backup`(Dropbox)에 저장
- 재배포 시 `entrypoint.sh`가 자동 복원
- `sqlite3.backup()`은 DB 사용 중에도 안전하게 동작

> 재배포와 마지막 백업 사이(최대 10분)에 생성된 채팅/설정은 유실될 수 있습니다.

### Qdrant 스냅샷 기반 영속성

- Qdrant 스토리지는 컨테이너 **로컬 디스크** 유지
- 10분 주기로 스냅샷 파일을 `/snapshots`(Dropbox)에 저장
- 재배포 시 `snapshot.sh`가 자동 복원
- v1.17.0에서 스냅샷 생성 중 쓰기 블로킹 제거 — RAG 동작에 영향 없음

> 재배포와 마지막 스냅샷 사이(최대 10분)에 추가된 파일은 재업로드가 필요합니다.
