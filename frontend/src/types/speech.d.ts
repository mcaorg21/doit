// lib.dom.d.ts (this TS version) declares SpeechRecognitionEvent/ErrorEvent/etc.
// but NOT the SpeechRecognition interface/constructor itself, nor
// window.SpeechRecognition/webkitSpeechRecognition — Chrome-only APIs that never
// made it into a W3C spec these lib.dom.d.ts snapshots track. Filled in here.
export {}

interface SpeechRecognition extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognition
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
}
