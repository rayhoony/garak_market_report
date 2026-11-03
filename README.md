# garak_market_report

## cron-job.org로 정기 실행하기

GitHub Actions의 `schedule`은 시작이 몇 시간씩 늦어지는 경우가 많아, cron-job.org가 정해진 시각에
GitHub API로 `post-cafe` 워크플로를 실행(workflow dispatch)하도록 한다.

기존 GitHub `schedule`은 예비로 그대로 둔다. 스케줄 실행은 오늘(KST) 같은 그룹을 수동·외부 실행으로
이미 게시했거나 게시 중이면 `check` 잡에서 건너뛰므로 중복 게시되지 않는다.
(외부 실행이 실패했다면 스케줄 실행이 대신 게시한다.)

### 1. GitHub 토큰 만들기

GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token

- Repository access: **Only select repositories** → `garak_market_report`
- Permissions → Repository permissions → **Actions: Read and write**
- 만료일을 정했다면 만료 전에 새 토큰으로 바꿔 줘야 한다.

### 2. cron-job.org 작업 만들기 (그룹마다 1개씩, 총 2개)

| 항목 | 값 |
|---|---|
| URL | `https://api.github.com/repos/rayhoony/garak_market_report/actions/workflows/post-cafe.yml/dispatches` |
| 실행 시각 | ITEMS_FIRST: 월~토 05:56 / ITEMS_SECOND: 월~토 09:54 (시간대 **Asia/Seoul**) |
| Advanced → Request method | `POST` |
| Advanced → Headers | `Accept: application/vnd.github+json`<br>`Authorization: Bearer <1번에서 만든 토큰>`<br>`X-GitHub-Api-Version: 2022-11-28`<br>`Content-Type: application/json` |
| Advanced → Request body | ITEMS_FIRST: `{"ref":"main","inputs":{"group":"first"}}`<br>ITEMS_SECOND: `{"ref":"main","inputs":{"group":"second"}}` |

- 성공하면 GitHub가 **204 No Content**를 돌려준다. cron-job.org의 "Test run"으로 확인할 수 있다.
- 401/403이면 토큰 권한·만료를, 404면 URL의 저장소·워크플로 파일 이름을, 422면 body의 `ref`·`group` 값을 확인한다.
- 실행 결과는 Actions 탭에서 `post-cafe group=first (workflow_dispatch)` 같은 제목으로 보인다.

### 3. 다 되면

cron-job.org 실행이 안정적으로 돌면 `.github/workflows/post-cafe.yml`의 `schedule` 블록을 지워도 된다.
(지우지 않아도 중복 게시는 되지 않는다.)
