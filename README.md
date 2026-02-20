# Daily News Digest

매일 아침 7시 (KST), 아래 12개 매체의 헤드라인을 Gmail로 발송합니다.

| 매체 | 방식 |
|------|------|
| The Verge | RSS |
| TechCrunch | RSS |
| Wired | RSS |
| 404 Media | RSS |
| Bloomberg | RSS |
| Business Insider | RSS |
| Fortune | RSS |
| Forbes | RSS |
| New York Times | RSS |
| WSJ | RSS |
| TradedVC | RSS |
| Google Trends | RSS (US Trending Searches) |

---

## 세팅 방법 (5분 소요)

### 1. Gmail 앱 비밀번호 발급

1. Google 계정 → **보안** → **2단계 인증** 활성화 (아직 안 했다면)
2. [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) 접속
3. 앱 이름 입력 (예: `news-digest`) → **만들기**
4. 생성된 16자리 비밀번호 복사해두기

### 2. GitHub 저장소 만들기

```bash
cd /Users/johyeri/news-digest
git init
git add .
git commit -m "init: daily news digest"
# GitHub에서 새 private 저장소 만든 후:
git remote add origin https://github.com/YOUR_USERNAME/news-digest.git
git push -u origin main
```

### 3. GitHub Secrets 등록

저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름 | 값 |
|-------------|-----|
| `GMAIL_ADDRESS` | 발송에 쓸 Gmail 주소 (예: `you@gmail.com`) |
| `GMAIL_APP_PASSWORD` | 위에서 발급한 16자리 앱 비밀번호 |
| `RECIPIENT_EMAIL` | 받을 이메일 주소 (본인 주소면 생략 가능) |

### 4. 테스트 실행

GitHub → **Actions** 탭 → `Daily News Digest` → **Run workflow** 클릭

이메일이 오면 완료!

---

## 로컬에서 실행하기

```bash
pip install feedparser

export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export RECIPIENT_EMAIL="you@gmail.com"

python fetch_digest.py
```

## 커스터마이징

- **발송 시간 변경**: `daily_digest.yml`의 `cron` 값 수정
  - 오전 8시 KST → `'0 23 * * *'`
  - 오전 9시 KST → `'0 0 * * *'`
- **매체 추가/제거**: `fetch_digest.py`의 `FEEDS` 딕셔너리 수정
- **기사 수 조정**: `MAX_ARTICLES` 값 변경 (기본 15개)
- **시간 범위 조정**: `HOURS_LOOKBACK` 값 변경 (기본 24시간)
