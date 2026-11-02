import { useCallback, useEffect, useRef, useState } from 'react'

/** Why the camera cannot start; each maps to one sentence the Playground can show inline. */
export type CameraError = 'insecure' | 'unsupported' | 'denied' | 'missing' | 'failed' | null

const MESSAGES: Record<Exclude<CameraError, null>, string> = {
  insecure: 'The camera needs HTTPS or localhost. Choose a file instead.',
  unsupported: 'This browser has no camera input. Choose a file instead.',
  denied: 'Camera permission was denied. Choose a file instead.',
  missing: 'No camera was found. Choose a file instead.',
  failed: 'The camera could not start. Choose a file instead.',
}

const errorFor = (e: unknown): Exclude<CameraError, null> => {
  const name = e instanceof DOMException ? e.name : (e as { name?: string } | null)?.name ?? ''
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'denied'
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'missing'
  if (name === 'NotSupportedError' || name === 'TypeError') return 'unsupported'
  return 'failed'
}

/**
 * Camera input for the Playground: nothing starts until the user asks, one frame becomes a File
 * that goes through the same predict path as an upload, and every track stops after capture.
 */
export function useCamera(onFrame: (file: File) => void) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [active, setActive] = useState(false)
  const [error, setError] = useState<CameraError>(null)

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setActive(false)
  }, [])

  useEffect(() => stop, [stop])              // leaving the page must never leave the camera on

  const start = useCallback(async () => {
    setError(null)
    if (!window.isSecureContext) { setError('insecure'); return }
    if (!navigator.mediaDevices?.getUserMedia) { setError('unsupported'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      streamRef.current = stream
      const video = videoRef.current
      if (!video) { stop(); return }
      video.srcObject = stream
      await video.play()
      setActive(true)
    } catch (e) {
      setError(errorFor(e))
      stop()
    }
  }, [stop])

  const capture = useCallback(() => {
    const video = videoRef.current
    if (!video?.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d')?.drawImage(video, 0, 0)
    canvas.toBlob((blob) => {
      if (!blob) { setError('failed'); stop(); return }
      onFrame(new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' }))
      stop()
    }, 'image/jpeg', 0.92)
  }, [onFrame, stop])

  return { videoRef, active, error, message: error ? MESSAGES[error] : '', start, stop, capture }
}
