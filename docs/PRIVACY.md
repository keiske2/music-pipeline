# Privacy Policy — music uploader

_Last updated: 2026-10-26_

**music uploader** is a personal automation tool run by the owner of this repository
(`keiske2/music-pipeline`) for their own YouTube channel. It is not offered to other users.

## What the app accesses

| Google permission (scope) | Why it is used |
|---|---|
| `https://www.googleapis.com/auth/youtube.upload` | Upload videos the owner created to the owner's own YouTube channel |
| `https://www.googleapis.com/auth/drive.readonly` | Read audio files the owner saved in their own Google Drive, to turn them into videos |

## How data is used

- Data is used only to read the owner's own audio files and upload the owner's own videos.
- No data is sold, shared with third parties, or used for advertising.
- No data from other Google users is collected.
- OAuth credentials are stored as private environment secrets and are never published.

## Retention and deletion

- Downloaded audio and generated videos are temporary working files and are deleted
  when the processing environment ends.
- Access can be revoked at any time from Google Account → Security →
  Third-party apps with account access → "music uploader".

## Google API Services User Data Policy

Use of information received from Google APIs adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements.

## Contact

Questions: open an issue at <https://github.com/keiske2/music-pipeline/issues>.

---

# 개인정보처리방침 — music uploader

**music uploader**는 이 저장소 소유자가 **본인 유튜브 채널**을 위해 쓰는 개인용 자동화 도구이며,
다른 사용자에게 제공하지 않습니다.

- **youtube.upload**: 소유자가 만든 영상을 소유자 본인 채널에 업로드
- **drive.readonly**: 소유자 본인 구글 드라이브의 음원 파일을 읽어 영상 제작
- 데이터는 판매·제3자 공유·광고에 사용하지 않으며, 다른 구글 사용자의 데이터는 수집하지 않습니다.
- 인증 정보는 비공개 환경 비밀값으로만 보관합니다.
- 작업 중 생성된 파일은 처리 환경이 종료되면 삭제됩니다.
- 권한 해제: Google 계정 → 보안 → 타사 앱 액세스 → "music uploader"
- 문의: <https://github.com/keiske2/music-pipeline/issues>
