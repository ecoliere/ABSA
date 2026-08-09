import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router';
import { Loader2 } from 'lucide-react';

export default function ProcessingPage() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!sessionId || !token) {
      navigate('/');
      return;
    }
    const sessions = JSON.parse(localStorage.getItem('my_sessions') || '[]');
    const sessionExists = sessions.some((s: any) => s.id === parseInt(sessionId));
    if (!sessionExists) {
      navigate('/');
      return;
    }
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setTimeout(() => {
            navigate(`/results/${sessionId}?token=${encodeURIComponent(token)}`);
          }, 500);
          return 100;
        }
        return prev + 10;
      });
    }, 200);

    return () => clearInterval(interval);
  }, [navigate, sessionId, token]);

  return (
    <div className="min-h-screen bg-zinc-50 flex items-center justify-center">
      <div className="w-full max-w-2xl px-8">
        <div className="bg-white border border-zinc-300 rounded p-12">
          <div className="flex flex-col items-center">
            <Loader2 className="w-12 h-12 text-zinc-900 animate-spin mb-6" />
            <h2 className="text-xl font-medium text-zinc-900 mb-2">Идёт анализ</h2>
            <p className="text-sm text-zinc-600 mb-8">Обрабатываем отзывы и извлекаем аспекты</p>

            <div className="w-full">
              <div className="h-2 bg-zinc-200 rounded overflow-hidden">
                <div
                  className="h-full bg-zinc-900 transition-all duration-200"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-xs text-zinc-500 mt-2 text-center">{progress}%</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}