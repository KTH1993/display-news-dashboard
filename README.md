# Display News Dashboard

유비리서치넷 · KDIA 일일뉴스 · 삼성디스플레이 뉴스룸 · LG디스플레이 소식을
GitHub Actions가 주기적으로(기본 4시간마다) 크롤링해 정적 대시보드로 보여줍니다.

- `index.html` — 대시보드 화면 (data/news.json을 fetch해서 렌더링)
- `data/news.json` — 실제 표시되는 데이터 (Actions가 자동 갱신)
- `scripts/scrape.py` — 4개 사이트를 크롤링하는 파이썬 스크립트
- `.github/workflows/update.yml` — 주기 실행 + 자동 커밋/푸시

---

## 1. GitHub에 레포 만들고 올리기

```bash
# 압축 풀었던 폴더로 이동
cd display-news-dashboard

git init
git add .
git commit -m "init: display news dashboard"

# GitHub에서 새 레포를 만든 뒤 (Add README 체크 해제) 주소를 아래에 연결
git branch -M main
git remote add origin https://github.com/<본인계정>/<레포이름>.git
git push -u origin main
```

## 2. GitHub Pages 켜기

1. 레포 → **Settings → Pages**
2. **Source**: `Deploy from a branch`
3. **Branch**: `main` / `(root)` 선택 → Save
4. 1~2분 후 `https://<계정>.github.io/<레포이름>/` 에서 확인 가능

## 3. Actions가 push 권한을 갖도록 설정

1. 레포 → **Settings → Actions → General**
2. 아래쪽 **Workflow permissions**에서
   **"Read and write permissions"** 선택 → Save
   *(이게 꺼져 있으면 스크래퍼가 파일을 못 커밋합니다)*

## 4. 수동으로 한 번 실행해보기 (테스트)

레포 → **Actions** 탭 → `Update display news data` 워크플로우 선택 →
**Run workflow** 버튼으로 즉시 1회 실행할 수 있습니다.
로그에서 각 소스별 `[OK]` / `[FAIL]` 결과를 확인하세요.

## 5. 업데이트 주기 바꾸기

`.github/workflows/update.yml`의 cron 값을 수정하면 됩니다. (UTC 기준)

```yaml
- cron: "0 */4 * * *"   # 4시간마다
- cron: "0 0 * * *"     # 매일 00:00 UTC(=09:00 KST) 1회
- cron: "0 0,9 * * *"   # 매일 09:00 KST / 18:00 KST
```

---

## ⚠️ 알아두어야 할 점

- **완전한 "실시간"은 아닙니다.** 정적 사이트라 서버가 없고, GitHub Actions가
  주기적으로 데이터를 갱신하는 방식입니다. 페이지를 열면 그 시점까지 갱신된
  `news.json`을 보여줍니다.
- **`scripts/scrape.py`의 CSS 셀렉터는 최선의 추정치입니다.** 4개 사이트 모두
  마크업 구조를 완전히 검증하지 못한 상태로 작성되었기 때문에, 실제 실행 시
  일부 소스에서 항목이 비거나 어긋날 수 있습니다. Actions 로그의 `[FAIL]`
  메시지를 캡처해서 알려주시면 셀렉터를 같이 고칠 수 있어요.
- 한 소스가 실패해도 다른 소스는 정상 갱신되며, 실패한 소스는 새로 비우지
  않고 직전 `news.json`의 내용을 그대로 유지합니다.
- LG디스플레이는 `news.lgdisplay.com`이 자바스크립트로 콘텐츠를 그리는
  방식이라 단순 크롤링이 통하지 않아, 서버 렌더링되는 공식
  `lgdisplay.com` 보도자료 페이지를 대신 수집합니다.
