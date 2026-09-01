# GoodNotesRestoreApp

이 폴더는 iPad에서 이미지를 선택하고 H2I FastAPI 서버를 통해 GoodNotes pasteboard binary를 받아 `UIPasteboard`에 기록하는 SwiftUI 앱이다.

Xcode에서는 다음 파일을 열면 된다.

```text
frontend/ipados/GoodNotesRestoreApp.xcodeproj
```

앱 흐름은 다음과 같다.

```text
이미지 선택
→ JPEG 업로드
→ job 상태 polling
→ GoodNotes binary 다운로드
→ UIPasteboard에 com.goodnotesapp.goodnotes5.notes 타입으로 기록
→ 서버에 delivered 보고
```

```text
frontend/ipados/GoodNotesRestoreApp/GoodNotesRestoreApp.swift
frontend/ipados/GoodNotesRestoreApp/ContentView.swift
frontend/ipados/GoodNotesRestoreApp/APIClient.swift
frontend/ipados/GoodNotesRestoreApp/Models.swift
frontend/ipados/GoodNotesRestoreApp/PasteboardWriter.swift
```

기본 서버 URL은 Railway 배포 주소인 `https://handwriting2ink-production.up.railway.app`이다. 로컬 FastAPI 서버를 iPad에서 직접 테스트하려면 `127.0.0.1` 대신 Mac의 LAN IP 주소를 입력해야 한다.

실기기 실행 시 Xcode에서 Team과 Bundle Identifier를 본인 계정에 맞게 조정해야 한다.
