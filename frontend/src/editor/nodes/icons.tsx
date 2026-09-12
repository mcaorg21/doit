import type { IconType } from 'react-icons'
import { SiGooglechrome } from 'react-icons/si'
import {
  LuGlobe,
  LuCircleX,
  LuNavigation,
  LuRectangleEllipsis,
  LuChevronsUpDown,
  LuMousePointerClick,
  LuMousePointer2,
  LuClock,
  LuCalendarClock,
  LuScanSearch,
  LuScanText,
  LuSplit,
  LuPause,
  LuFrame,
  LuRepeat,
  LuRows3,
  LuBox,
  LuWebhook,
  LuListChecks,
  LuPuzzle,
  LuCircleHelp,
  LuCloud,
  LuSave,
  LuFolderOpen,
  LuUpload,
  LuShieldCheck,
  LuDownload,
  LuCookie,
  LuLogIn,
  LuListTree,
} from 'react-icons/lu'

// One specific, deliberately-picked icon per node type — Lucide for general/functional
// icons, Simple Icons for the Chrome brand mark (open_browser).
const ICONS: Record<string, IconType> = {
  globe: LuGlobe, // HTTP Request
  chrome: SiGooglechrome, // Open Browser
  'circle-x': LuCircleX, // Close Browser
  navigation: LuNavigation, // Navigate
  'rectangle-ellipsis': LuRectangleEllipsis, // Fill Input
  'chevrons-up-down': LuChevronsUpDown, // Select Option
  'mouse-pointer-click': LuMousePointerClick, // Click
  'mouse-pointer-2': LuMousePointer2, // Hover
  clock: LuClock, // Wait
  schedule: LuCalendarClock, // Schedule Trigger
  webhook: LuWebhook, // Webhook Trigger
  'scan-search': LuScanSearch, // Element Present?
  'scan-text': LuScanText, // Get Text
  split: LuSplit, // IF
  pause: LuPause, // Pause (debugger)
  frame: LuFrame, // Switch Frame
  repeat: LuRepeat, // Loop
  rows: LuRows3, // Multi Input
  'list-checks': LuListChecks, // Multi Click
  puzzle: LuPuzzle, // 2Captcha
  'help-circle': LuCircleHelp, // Unknown (from AI import)
  cloud: LuCloud, // Browser (2Captcha)
  save: LuSave, // Save Files
  'folder-open': LuFolderOpen, // Get File
  upload: LuUpload, // Upload File
  'shield-check': LuShieldCheck, // 2FA Code (TOTP)
  download: LuDownload, // Download File
  cookie: LuCookie, // Save Cookies / Load Cookies
  'log-in': LuLogIn, // Login
  'list-select': LuListTree, // Select List HTML
}

// LuSplit's glyph reads top-to-bottom (a path forking upward) — the canvas flows
// left-to-right now, so it needs a quarter turn to actually point the way the branches
// (true/false) come out of the node.
const ROTATE: Record<string, number> = {
  split: 90,
}

export default function NodeIcon({ name, size = 24 }: { name?: string | null; size?: number }) {
  const Icon = (name && ICONS[name]) || LuBox
  const rotation = (name && ROTATE[name]) || 0
  return <Icon size={size} style={rotation ? { transform: `rotate(${rotation}deg)` } : undefined} />
}
