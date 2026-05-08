# Frontend — AI-Powered CV Analysis Platform

> React 19 + Vite + TypeScript + Tailwind CSS — Modern SPA for resume analysis & ATS scoring.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Pages & Routes](#pages--routes)
- [Architecture](#architecture)
- [Components](#components)
- [API Integration](#api-integration)
- [Theming](#theming)
- [Deployment](#deployment)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Framework** | React 19 + TypeScript 6 |
| **Build Tool** | Vite 8 |
| **Styling** | Tailwind CSS 3.4 |
| **UI Primitives** | Radix UI (Dialog, Select, Tabs, Dropdown, etc.) |
| **Routing** | React Router DOM 7 |
| **State / Data** | TanStack React Query 5 |
| **Forms** | React Hook Form + Zod validation |
| **Charts** | Recharts 3 |
| **Animations** | Framer Motion |
| **Icons** | Lucide React |
| **Notifications** | Sonner (toast) |

---

## Project Structure

```
Frontend/
├── public/
│   ├── favicon.svg
│   └── icons.svg
│
├── src/
│   ├── main.tsx                # App entry point
│   ├── App.tsx                 # Root component (routing + providers)
│   ├── App.css                 # Global app styles
│   ├── index.css               # Tailwind base + CSS variables
│   │
│   ├── api/                    # Backend API functions
│   │   ├── auth.ts             #   Login, register, refresh
│   │   ├── users.ts            #   User profile
│   │   ├── resumes.ts          #   Resume upload & listing
│   │   ├── jobs.ts             #   Job description CRUD
│   │   └── analysis.ts         #   Analysis trigger & results
│   │
│   ├── components/
│   │   ├── ui/                 # Reusable UI primitives (Radix-based)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── input.tsx
│   │   │   ├── select.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── badge.tsx
│   │   │   ├── avatar.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   ├── label.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── separator.tsx
│   │   │   ├── sheet.tsx       #   Mobile slide-out panel
│   │   │   ├── skeleton.tsx    #   Loading placeholders
│   │   │   └── textarea.tsx
│   │   │
│   │   ├── features/           # Domain-specific components
│   │   │   ├── upload-dropzone.tsx       # Drag-and-drop resume upload
│   │   │   ├── score-radar-chart.tsx     # Score breakdown visualization
│   │   │   └── analysis-status-badge.tsx # Status indicator
│   │   │
│   │   └── layout/             # App shell & navigation
│   │       ├── app-shell.tsx   #   Main layout wrapper
│   │       ├── header.tsx      #   Top nav bar
│   │       ├── sidebar.tsx     #   Side navigation
│   │       └── protected-route.tsx  # Auth guard
│   │
│   ├── contexts/               # React Context providers
│   │   ├── auth-context.tsx    #   Authentication state
│   │   └── theme-context.tsx   #   Dark/light theme toggle
│   │
│   ├── lib/                    # Core utilities
│   │   ├── fetch-client.ts     #   API fetch wrapper (auto-refresh JWT)
│   │   ├── query-client.ts     #   TanStack Query config
│   │   └── utils.ts            #   cn(), formatDate, etc.
│   │
│   ├── pages/                  # Route-level page components
│   │   ├── login-page.tsx
│   │   ├── signup-page.tsx
│   │   ├── dashboard-page.tsx
│   │   ├── resumes-page.tsx
│   │   ├── jobs-page.tsx
│   │   ├── analysis-page.tsx
│   │   ├── analysis-detail-page.tsx
│   │   └── profile-page.tsx
│   │
│   ├── types/                  # TypeScript type definitions
│   │   ├── auth.ts
│   │   ├── user.ts
│   │   ├── resume.ts
│   │   ├── job.ts
│   │   ├── analysis.ts
│   │   └── common.ts
│   │
│   └── assets/                 # Static assets (images, SVGs)
│
├── index.html                  # HTML entry
├── vite.config.ts              # Vite config (proxy to backend)
├── tailwind.config.js          # Tailwind theme
├── tsconfig.json               # TypeScript config
├── eslint.config.js            # Linting rules
├── postcss.config.js
└── package.json
```

---

## Getting Started

### Prerequisites

- Node.js 18+
- npm 9+

### Installation

```bash
# 1. Install dependencies
npm install

# 2. Start dev server
npm run dev
```

App runs at: **http://localhost:5173**

> The Vite dev server proxies `/api/*` requests to `http://localhost:8000` (Backend).

### Build for Production

```bash
npm run build     # Output in dist/
npm run preview   # Preview production build locally
```

---

## Pages & Routes

| Route | Page | Auth | Description |
|-------|------|------|-------------|
| `/login` | LoginPage | ❌ | Email + password login |
| `/signup` | SignupPage | ❌ | Account registration |
| `/` | DashboardPage | ✅ | Overview stats, recent activity |
| `/resumes` | ResumesPage | ✅ | Upload & manage resumes |
| `/jobs` | JobsPage | ✅ | Create & manage job descriptions |
| `/analysis` | AnalysisPage | ✅ | Run & view analyses |
| `/analysis/:id` | AnalysisDetailPage | ✅ | Detailed results, scores, feedback |
| `/profile` | ProfilePage | ✅ | Account settings |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                      App.tsx                         │
│  ┌─────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ AuthContext  │  │ ThemeCtx  │  │ QueryClient   │  │
│  └──────┬──────┘  └────┬─────┘  └───────┬───────┘  │
│         └──────────────┼────────────────┘           │
│                        │                            │
│  ┌─────────────────────▼────────────────────────┐   │
│  │              React Router                     │   │
│  │  ┌─────────────────────────────────────────┐  │   │
│  │  │  ProtectedRoute → AppShell              │  │   │
│  │  │  ┌───────────┐  ┌────────────────────┐  │  │   │
│  │  │  │  Sidebar   │  │  Page Component    │  │  │   │
│  │  │  │  Header    │  │  └─ api/*          │  │  │   │
│  │  │  │            │  │  └─ components/*   │  │  │   │
│  │  │  └───────────┘  └────────────────────┘  │  │   │
│  │  └─────────────────────────────────────────┘  │   │
│  └───────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                         │
                    fetch('/api/*')
                         │
                    ┌────▼────┐
                    │ Backend │
                    │ :8000   │
                    └─────────┘
```

### Data Flow

1. **Pages** call functions from `api/*.ts`
2. **API functions** use `lib/fetch-client.ts` (auto-attaches JWT, handles 401 refresh)
3. **TanStack Query** manages caching, refetching, and loading states
4. **Components** consume query data and render UI

---

## Components

### UI Primitives (`components/ui/`)

Built on [Radix UI](https://radix-ui.com/) + [class-variance-authority](https://cva.style/) for accessible, unstyled base components styled with Tailwind:

| Component | Radix Primitive | Usage |
|-----------|----------------|-------|
| Button | Slot | Actions, form submit |
| Dialog | Dialog | Modals, confirmations |
| Select | Select | Dropdowns |
| Tabs | Tabs | Tab navigation |
| Sheet | Dialog | Mobile sidebar |
| DropdownMenu | DropdownMenu | Context menus |
| Progress | Progress | Upload/analysis progress |

### Feature Components (`components/features/`)

| Component | Description |
|-----------|-------------|
| `UploadDropzone` | Drag-and-drop resume upload with file validation |
| `ScoreRadarChart` | Recharts radar chart for score breakdown |
| `AnalysisStatusBadge` | Color-coded status indicator (QUEUED → DONE) |

### Layout (`components/layout/`)

| Component | Description |
|-----------|-------------|
| `AppShell` | Main layout (sidebar + header + content) |
| `Header` | Top bar with user menu, theme toggle |
| `Sidebar` | Navigation links (responsive, mobile sheet) |
| `ProtectedRoute` | Redirects to `/login` if unauthenticated |

---

## API Integration

All API calls go through `lib/fetch-client.ts`:

- **Auto-auth**: Attaches `Authorization: Bearer <token>` to every request
- **Auto-refresh**: On 401, transparently refreshes the JWT and retries
- **Typed responses**: All endpoints return `APIResponse<T>` and extract `.data`
- **Error handling**: Throws `ApiError` with status, message, and details

```typescript
// Example: fetching analyses
import { api } from '@/lib/fetch-client'
import type { Analysis } from '@/types/analysis'

const analyses = await api.get<Analysis[]>('/api/v1/analysis')
```

---

## Theming

- **Dark/Light mode** via `ThemeContext` (persisted in `localStorage`)
- **CSS variables** defined in `index.css` for colors, radii, spacing
- **Tailwind config** extends default theme with custom design tokens

---

## Deployment

### Render (Static Site)

| Setting | Value |
|---------|-------|
| **Root Directory** | `Frontend` |
| **Build Command** | `npm install && npm run build` |
| **Publish Directory** | `Frontend/dist` |
| **Redirect Rule** | `/* → /index.html` (200) — for SPA routing |

### Environment Variables

Set `VITE_API_URL` if the backend is on a different domain:

```env
VITE_API_URL=https://your-backend.onrender.com
```

> For same-domain deployments (Nginx reverse proxy), no env vars are needed — the relative `/api/*` paths work automatically.
