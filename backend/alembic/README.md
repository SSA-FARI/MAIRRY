# Database migrations

Alembic은 `app.core.database.Base.metadata`를 사용하며 `app.domains` 아래 이름이 `models.py`인 모듈을
자동으로 import한다. 기능 담당자는 자신의 도메인에 모델과 migration을 함께 추가한다.

```text
app/domains/wedding_plan/models.py  # A
app/domains/documents/models.py     # B
app/domains/contracts/models.py     # C
```

## 새 migration

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c alembic.ini revision --autogenerate -m "add wedding plan"
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

생성된 migration의 upgrade와 downgrade를 직접 검토한다. Repository는 임의로 commit하지 않고
Service가 트랜잭션을 소유한다. 여러 migration head가 생기면 임의로 파일을 다시 만들지 말고 D와
영향 담당자가 함께 merge migration 여부를 결정한다.
