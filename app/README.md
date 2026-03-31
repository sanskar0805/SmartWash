# App — Student Mobile Interface

Flutter-based cross-platform app (Android + iOS) for students to check machine status, book slots, and receive notifications.

## Folder Structure

```
app/
├── lib/          ← Flutter Dart source files (coming soon)
│   └── main.dart
├── screens/      ← Screen-level components (coming soon)
└── assets/       ← Icons and images
```

## Key Screens (Planned)

| Screen | What the Student Sees |
|---|---|
| Home / Machine Map | Live grid: 🟢 Free · 🔵 Running · 🔴 Faulty · 🟡 Done |
| Machine Detail | Time remaining, queue, option to book |
| Book a Slot | Pick machine + time, system confirms |
| Notifications | Cycle done alert · Clothes collection reminder |
| Report Fault | One-tap fault report to admin |

## Tech

- **Framework:** Flutter (Dart) — free, cross-platform
- **State Management:** Provider or Riverpod (decision pending)
- **Backend connection:** Firebase Realtime Database + REST API
- **Notifications:** Firebase Cloud Messaging (FCM)

## Status: Pending — to be built during Phase 4
