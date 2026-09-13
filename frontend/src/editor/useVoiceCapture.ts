import { useCallback, useEffect, useRef, useState } from 'react'

// Chrome-only (see src/types/speech.d.ts for why the constructor isn't in
// lib.dom.d.ts) — every error message below ends by pointing at the textarea as the
// always-available fallback, since !supported or a mid-recording error must never
// leave the human stuck with no way to answer.
function mapSpeechError(code: string): string {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Permissão de microfone negada — permita o acesso ao microfone nas configurações do navegador, ou digite a resposta manualmente abaixo.'
    case 'no-speech':
      return 'Nenhuma fala detectada — tente gravar de novo, ou digite a resposta manualmente abaixo.'
    case 'network':
      return 'Erro de rede no reconhecimento de voz — tente de novo, ou digite a resposta manualmente abaixo.'
    default:
      return `Erro no reconhecimento de voz (${code}) — digite a resposta manualmente abaixo.`
  }
}

export interface VoiceCapture {
  recording: boolean
  transcript: string
  setTranscript: (value: string) => void
  interim: string
  error: string | null
  supported: boolean
  start: () => void
  stop: () => void
  reset: () => void
}

export function useVoiceCapture(): VoiceCapture {
  const [recording, setRecording] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [interim, setInterim] = useState('')
  const [error, setError] = useState<string | null>(null)
  const recognitionRef = useRef<SpeechRecognition | null>(null)

  const supported = typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition)

  const start = useCallback(() => {
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!Ctor) {
      setError(mapSpeechError('not-supported'))
      return
    }
    setError(null)
    setInterim('')
    const recognition = new Ctor()
    recognition.lang = 'pt-BR'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.onresult = (event) => {
      let finalChunk = ''
      let interimChunk = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) finalChunk += result[0].transcript
        else interimChunk += result[0].transcript
      }
      if (finalChunk) setTranscript((prev) => (prev ? `${prev} ${finalChunk}`.trim() : finalChunk.trim()))
      setInterim(interimChunk)
    }
    recognition.onerror = (event) => {
      setError(mapSpeechError(event.error))
      setRecording(false)
    }
    recognition.onend = () => {
      setRecording(false)
      setInterim('')
    }
    recognitionRef.current = recognition
    recognition.start()
    setRecording(true)
  }, [])

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
  }, [])

  const reset = useCallback(() => {
    setTranscript('')
    setInterim('')
    setError(null)
  }, [])

  // Never leave the mic hot if the modal using this hook unmounts mid-recording.
  useEffect(() => () => recognitionRef.current?.stop(), [])

  return { recording, transcript, setTranscript, interim, error, supported, start, stop, reset }
}
