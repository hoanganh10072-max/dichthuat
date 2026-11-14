import { useState } from 'react';
import { Image, Languages } from 'lucide-react';

export default function ImagePreview({ url, name }: { url: string; name: string }) {
  const [view, setView] = useState<'image' | 'ocr'>('image');
  return <div className={`image-preview-controls view-${view}`}>
    <div className="source-views" role="group" aria-label="Nội dung nguồn">
      <button aria-pressed={view === 'image'} onClick={() => setView('image')}><Image size={14}/>Ảnh gốc</button>
      <button aria-pressed={view === 'ocr'} onClick={() => setView('ocr')}><Languages size={14}/>Chữ trong ảnh</button>
    </div>
    {view === 'image' && <div className="source-image"><img src={url} alt={`Ảnh gốc: ${name}`}/></div>}
  </div>;
}
