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
  LuScanSearch,
  LuSplit,
  LuPause,
  LuBox,
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
  'scan-search': LuScanSearch, // Element Present?
  split: LuSplit, // IF
  pause: LuPause, // Pause (debugger)
}

export default function NodeIcon({ name, size = 24 }: { name?: string | null; size?: number }) {
  const Icon = (name && ICONS[name]) || LuBox
  return <Icon size={size} />
}
