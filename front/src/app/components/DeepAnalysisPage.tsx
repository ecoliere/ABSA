import { useNavigate, useParams, useSearchParams } from 'react-router';
import { ArrowLeft, Download, ThumbsDown, ThumbsUp, Loader2, ChevronDown, ChevronRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { apiGet } from '../../api/client';

interface ReasonGroup {
  name: string;
  total_frequency: number;
  members_with_freq: { reason: string; count: number }[];
}

interface DeepAnalysisData {
  aspect: string;
  total_mentions: number;
  average_score: number;
  praised_groups: ReasonGroup[];
  criticized_groups: ReasonGroup[];
  recommendation: string;
}

export default function DeepAnalysisPage() {
  const navigate = useNavigate();
  const { sessionId, aspect } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState<DeepAnalysisData | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const aspectName = decodeURIComponent(aspect || '');
  const aspectList = new URLSearchParams(window.location.search).get('aspects');
  const isGroup = !!aspectList;

  const toggleGroup = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  useEffect(() => {
    if (!sessionId || !aspect || !token) {
      navigate('/');
      return;
    }
    const sessions = JSON.parse(localStorage.getItem('my_sessions') || '[]');
    const sessionExists = sessions.some((s: any) => s.id === parseInt(sessionId));
    if (!sessionExists) {
      navigate('/');
      return;
    }
    const urlParams = new URLSearchParams(window.location.search);
    const aspectsParam = urlParams.get('aspects');

    let url = `/deep/${sessionId}/${encodeURIComponent(aspect)}`;
    if (aspectsParam) {
      url += `?aspects=${encodeURIComponent(aspectsParam)}`;
    }

    apiGet(url, token)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sessionId, aspect, token, navigate]);

  const handleDownload = () => {
    if (!data) return;

    import('xlsx').then((XLSX) => {
      // Лист 1: Общая информация
      const summaryData = [
        {
          Аспект: aspectName,
          'Всего упоминаний': data.total_mentions,
          'Групп позитива': data.praised_groups.length,
          'Групп негатива': data.criticized_groups.length,
        },
      ];

      // Лист 2: Группы позитива
      const praisedData: any[] = [];
      data.praised_groups.forEach((g) => {
        praisedData.push({
          Группа: g.name,
          'Общая частота': g.total_frequency,
        });
        g.members_with_freq.forEach((m) => {
          praisedData.push({
            Группа: '',
            'Общая частота': `  ${m.reason}`,
            _count: m.count,
          });
        });
      });

      // Лист 3: Группы негатива
      const criticizedData: any[] = [];
      data.criticized_groups.forEach((g) => {
        criticizedData.push({
          Группа: g.name,
          'Общая частота': g.total_frequency,
        });
        g.members_with_freq.forEach((m) => {
          criticizedData.push({
            Группа: '',
            'Общая частота': `  ${m.reason}`,
            _count: m.count,
          });
        });
      });

      // Лист 4: Рекомендация
      const recommendationData = [{ Рекомендация: data.recommendation }];

      const wsSummary = XLSX.utils.json_to_sheet(summaryData);
      const wsPraised = XLSX.utils.json_to_sheet(praisedData);
      const wsCriticized = XLSX.utils.json_to_sheet(criticizedData);
      const wsRecommendation = XLSX.utils.json_to_sheet(recommendationData);

      wsSummary['!cols'] = [{ wch: 25 }, { wch: 20 }, { wch: 20 }, { wch: 20 }];
      wsPraised['!cols'] = [{ wch: 30 }, { wch: 60 }];
      wsCriticized['!cols'] = [{ wch: 30 }, { wch: 60 }];
      wsRecommendation['!cols'] = [{ wch: 80 }];

      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, wsSummary, 'Общая информация');
      XLSX.utils.book_append_sheet(wb, wsPraised, 'Группы позитива');
      XLSX.utils.book_append_sheet(wb, wsCriticized, 'Группы негатива');
      XLSX.utils.book_append_sheet(wb, wsRecommendation, 'Рекомендация');

      XLSX.writeFile(
        wb,
        `deep_analysis_${aspectName}_${new Date().toISOString().split('T')[0]}.xlsx`
      );
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-50 flex items-center justify-center">
        <p className="text-red-500">Ошибка: {error}</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="min-h-screen bg-zinc-50">
      <div className="border-b border-zinc-300 bg-white">
        <div className="max-w-6xl mx-auto px-8 py-6">
          <button
            onClick={() => navigate(`/results/${sessionId}?token=${encodeURIComponent(token!)}`)}
            className="flex items-center gap-2 text-sm text-zinc-600 hover:text-zinc-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Назад к результатам
          </button>
          <h1 className="text-2xl font-medium text-zinc-900">
            Глубокий анализ: {aspectName} {isGroup ? '(группа)' : ''}
          </h1>
          <p className="text-sm text-zinc-600 mt-1">
            Детальный разбор упоминаний и причин оценок
          </p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-8 py-8">
        <div className="grid grid-cols-2 gap-6 mb-8">
          <div className="bg-white border border-zinc-300 rounded p-6">
            <div className="text-sm text-zinc-600 mb-1">Упоминания</div>
            <div className="text-3xl font-medium text-zinc-900">
              {data.total_mentions}
            </div>
          </div>
          <div className="bg-white border border-zinc-300 rounded p-6">
            <div className="text-sm text-zinc-600 mb-1">Средняя оценка</div>
            <div className="text-3xl font-medium text-zinc-900">
              {data.average_score !== undefined ? data.average_score.toFixed(1) : '—'}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 mb-8">
          <div className="bg-white border border-zinc-300 rounded">
            <div className="border-b border-zinc-300 px-6 py-4 flex items-center gap-2">
              <ThumbsDown className="w-5 h-5 text-red-600" />
              <h2 className="text-base font-medium text-zinc-900">Причины негатива</h2>
            </div>
            <div className="p-6 max-h-96 overflow-y-auto">
              {data.criticized_groups.length === 0 ? (
                <p className="text-sm text-zinc-500">Негативные причины не найдены</p>
              ) : (
                <div className="space-y-6">
                  {data.criticized_groups.map((group, idx) => {
                    const key = `neg-${idx}`;
                    const isExpanded = expanded[key] || false;
                    return (
                      <div key={idx}>
                        <div
                          className="flex items-center justify-between mb-2 cursor-pointer hover:bg-zinc-50 -mx-2 px-2 py-1 rounded"
                          onClick={() => toggleGroup(key)}
                        >
                          <span className="text-sm font-medium text-zinc-900">
                            {group.name}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 bg-red-50 text-red-700 text-xs font-medium rounded">
                              {group.total_frequency}
                            </span>
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-zinc-400" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-zinc-400" />
                            )}
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="space-y-1 pl-4 border-l-2 border-red-100">
                            {group.members_with_freq.map((item, i) => (
                              <div
                                key={i}
                                className="flex items-start justify-between text-sm"
                              >
                                <span className="text-zinc-600">{item.reason}</span>
                                <span className="ml-2 text-zinc-400">{item.count}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="bg-white border border-zinc-300 rounded">
            <div className="border-b border-zinc-300 px-6 py-4 flex items-center gap-2">
              <ThumbsUp className="w-5 h-5 text-green-600" />
              <h2 className="text-base font-medium text-zinc-900">Причины позитива</h2>
            </div>
            <div className="p-6 max-h-96 overflow-y-auto">
              {data.praised_groups.length === 0 ? (
                <p className="text-sm text-zinc-500">Позитивные причины не найдены</p>
              ) : (
                <div className="space-y-6">
                  {data.praised_groups.map((group, idx) => {
                    const key = `pos-${idx}`;
                    const isExpanded = expanded[key] || false;
                    return (
                      <div key={idx}>
                        <div
                          className="flex items-center justify-between mb-2 cursor-pointer hover:bg-zinc-50 -mx-2 px-2 py-1 rounded"
                          onClick={() => toggleGroup(key)}
                        >
                          <span className="text-sm font-medium text-zinc-900">
                            {group.name}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 bg-green-50 text-green-700 text-xs font-medium rounded">
                              {group.total_frequency}
                            </span>
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-zinc-400" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-zinc-400" />
                            )}
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="space-y-1 pl-4 border-l-2 border-green-100">
                            {group.members_with_freq.map((item, i) => (
                              <div
                                key={i}
                                className="flex items-start justify-between text-sm"
                              >
                                <span className="text-zinc-600">{item.reason}</span>
                                <span className="ml-2 text-zinc-400">{item.count}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="bg-white border border-zinc-300 rounded mb-8">
          <div className="border-b border-zinc-300 px-6 py-4">
            <h2 className="text-base font-medium text-zinc-900">Рекомендация</h2>
          </div>
          <div className="p-6">
            <p className="text-sm text-zinc-700 leading-relaxed">{data.recommendation}</p>
          </div>
        </div>

        <div className="flex justify-between">
          <button
            onClick={() => navigate(`/results/${sessionId}?token=${encodeURIComponent(token!)}`)}
            className="px-6 py-3 border border-zinc-300 rounded text-sm font-medium text-zinc-900 hover:bg-zinc-50"
          >
            Назад к результатам
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-6 py-3 bg-zinc-900 text-white text-sm font-medium rounded hover:bg-zinc-800"
          >
            <Download className="w-4 h-4" />
            Скачать детализацию
          </button>
        </div>
      </div>
    </div>
  );
}