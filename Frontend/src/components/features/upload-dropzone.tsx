import { useCallback, useState } from 'react'
import { UploadCloud, X, FileText, AlertCircle } from 'lucide-react'
import { cn, formatFileSize } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const ACCEPTED = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
const MAX_SIZE = 10 * 1024 * 1024 // 10MB

interface Props {
  onFileSelected: (file: File) => void
  isUploading?: boolean
}

export function UploadDropzone({ onFileSelected, isUploading = false }: Props) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)

  const validate = (f: File): string | null => {
    if (!ACCEPTED.includes(f.type)) return 'Only PDF, DOCX, and TXT files are accepted.'
    if (f.size > MAX_SIZE) return 'File size must be 10 MB or less.'
    return null
  }

  const handleFile = useCallback((f: File) => {
    const err = validate(f)
    if (err) { setError(err); return }
    setError(null)
    setFile(f)
    onFileSelected(f)
  }, [onFileSelected])

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) handleFile(f)
  }

  const clearFile = () => { setFile(null); setError(null) }

  if (file) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
        <FileText className="h-8 w-8 text-primary shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{file.name}</p>
          <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
        </div>
        {!isUploading && (
          <Button variant="ghost" size="icon" onClick={clearFile} aria-label="Remove file">
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    )
  }

  return (
    <div>
      <label
        htmlFor="resume-upload"
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-10 cursor-pointer transition-colors',
          dragging
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-primary/50 hover:bg-accent/50',
        )}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <UploadCloud className="h-6 w-6 text-primary" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium">Drop your resume here, or <span className="text-primary">browse</span></p>
          <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, TXT — max 10 MB</p>
        </div>
        <input
          id="resume-upload"
          type="file"
          className="sr-only"
          accept=".pdf,.docx,.txt"
          onChange={onInputChange}
        />
      </label>
      {error && (
        <p className="flex items-center gap-1.5 mt-2 text-xs text-destructive">
          <AlertCircle className="h-3.5 w-3.5" />
          {error}
        </p>
      )}
    </div>
  )
}
