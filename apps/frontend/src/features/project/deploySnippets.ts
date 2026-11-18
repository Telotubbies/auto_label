/** Code samples for the Deployments steps; pure so a node test can pin the strings. */
export type DeployLang = 'python' | 'javascript' | 'curl'
export type DeployKind = 'images' | 'video'

export const INSTALL: Record<DeployLang, string> = {
  python: 'pip install requests opencv-python',
  javascript: '# nothing to install: fetch is built into browsers and Node 18+',
  curl: '# nothing to install: curl ships with macOS, Linux and Windows 10+',
}

export function deploySnippet(kind: DeployKind, lang: DeployLang, endpoint: string): string {
  const url = `${endpoint}?api_key=`
  if (kind === 'images') {
    if (lang === 'python') return `import requests\n\nr = requests.post(\n    "${endpoint}",\n    params={"api_key": API_KEY, "confidence": 0.4},\n    files={"file": open("image.jpg", "rb")},\n)\nprint(r.json()["predictions"])`
    if (lang === 'javascript') return `const form = new FormData()\nform.append('file', fileInput.files[0])\nconst r = await fetch('${url}' + API_KEY, { method: 'POST', body: form })\nconst { predictions } = await r.json()`
    return `curl -X POST "${url}$LABELDESK_API_KEY&confidence=0.4" \\n  -F "file=@image.jpg"`
  }
  if (lang === 'python') return `import cv2, requests\n\ncap = cv2.VideoCapture("video.mp4")\nwhile True:\n    ok, frame = cap.read()\n    if not ok:\n        break\n    jpg = cv2.imencode(".jpg", frame)[1].tobytes()\n    r = requests.post("${endpoint}", params={"api_key": API_KEY}, files={"file": jpg})\n    print(r.json()["predictions"])`
  if (lang === 'javascript') return `const video = document.querySelector('video')\nconst canvas = document.createElement('canvas')\nsetInterval(async () => {\n  canvas.width = video.videoWidth; canvas.height = video.videoHeight\n  canvas.getContext('2d').drawImage(video, 0, 0)\n  const blob = await new Promise((ok) => canvas.toBlob(ok, 'image/jpeg'))\n  const form = new FormData(); form.append('file', blob)\n  const r = await fetch('${url}' + API_KEY, { method: 'POST', body: form })\n  console.log((await r.json()).predictions)\n}, 500)`
  return `ffmpeg -i video.mp4 -vf fps=1 frame_%04d.jpg\nfor f in frame_*.jpg; do\n  curl -s -X POST "${url}$LABELDESK_API_KEY" -F "file=@$f"\ndone`
}
