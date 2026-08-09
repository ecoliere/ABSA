import { useState, useRef } from 'react';
import { useNavigate } from 'react-router';
import { Upload, FileText, Loader2 } from 'lucide-react';
import { apiPost, apiUploadFile } from "../../api/client";

export default function HomePage() {
  const navigate = useNavigate();
  const [manualText, setManualText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleAnalyze = async () => {
    if (!manualText && !selectedFile) return;
    setLoading(true);
    try {
        let data;
        if (selectedFile) {
            data = await apiUploadFile('/upload', selectedFile);
        } else {
            data = await apiPost('/analyze-single', { text: manualText });
        }
        // Сохраняем объект { id, token } в localStorage
        const sessions = JSON.parse(localStorage.getItem('my_sessions') || '[]');
        sessions.push({ id: data.session_id, token: data.access_token });
        localStorage.setItem('my_sessions', JSON.stringify(sessions));
        
        if (selectedFile) {
            navigate(`/processing/${data.session_id}?token=${encodeURIComponent(data.access_token)}`);
        } else {
            navigate(`/results/${data.session_id}?token=${encodeURIComponent(data.access_token)}`);
        }
    } catch (err: any) {
        alert('Ошибка: ' + err.message);
    } finally {
        setLoading(false);
    }
};

  return (
    <div className="min-h-screen bg-zinc-50">
      <div className="border-b border-zinc-300 bg-white">
        <div className="max-w-5xl mx-auto px-8 py-6">
          <h1 className="text-2xl font-medium text-zinc-900">Анализ текстов</h1>
          <p className="text-sm text-zinc-600 mt-1">Инструмент анализа отзывов и тональности</p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-8 py-12">
        <div className="grid gap-8">
          <div className="bg-white border border-zinc-300 rounded">
            <div className="border-b border-zinc-300 px-6 py-4">
              <h2 className="text-base font-medium text-zinc-900">Загрузка CSV-файла</h2>
            </div>
            <div className="p-6">
              <label className="flex flex-col items-center justify-center border-2 border-dashed border-zinc-300 rounded h-48 cursor-pointer hover:border-zinc-400 transition-colors">
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  ref={fileInputRef}
                  className="hidden"
                />
                <Upload className="w-10 h-10 text-zinc-400 mb-3" />
                {selectedFile ? (
                  <div className="flex items-center gap-2 text-sm text-zinc-700">
                    <FileText className="w-4 h-4" />
                    <span>{selectedFile.name}</span>
                  </div>
                ) : (
                  <>
                    <span className="text-sm font-medium text-zinc-700">Выберите CSV-файл</span>
                    <span className="text-xs text-zinc-500 mt-1">или перетащите сюда</span>
                  </>
                )}
              </label>
              <p className="text-xs text-zinc-500 mt-3">
                Формат: CSV файл с колонкой отзывов
              </p>
            </div>
          </div>

          <div className="bg-white border border-zinc-300 rounded">
            <div className="border-b border-zinc-300 px-6 py-4">
              <h2 className="text-base font-medium text-zinc-900">Ручной ввод отзыва</h2>
            </div>
            <div className="p-6">
              <textarea
                value={manualText}
                onChange={(e) => setManualText(e.target.value)}
                placeholder="Введите текст отзыва для анализа..."
                className="w-full h-32 px-4 py-3 border border-zinc-300 rounded text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:border-transparent resize-none"
              />
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleAnalyze}
              disabled={(!selectedFile && !manualText) || loading}
              className="px-8 py-3 bg-zinc-900 text-white text-sm font-medium rounded hover:bg-zinc-800 transition-colors disabled:bg-zinc-300 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {loading ? 'Анализ...' : 'Начать анализ'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}