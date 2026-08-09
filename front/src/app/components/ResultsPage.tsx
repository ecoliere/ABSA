import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router';
import { ArrowLeft, Download, TrendingUp, TrendingDown, AlertCircle, Settings2, ChevronDown, ArrowUpDown, Loader2 } from 'lucide-react';
import MergeAspectModal from './MergeAspectModal';
import AspectChart from './AspectChart';
import { apiGet } from '../../api/client';

interface AspectData {
  name: string;
  total: number;
  positivity: number;
  negativity: number;
  positive_count?: number;
  neutral_count?: number;
  negative_count?: number;
  sentiment_score: number;
  average_score: number;
  sentiment: 'positive' | 'neutral' | 'negative';
}

interface ReviewData {
  id: number;
  text: string;
  topics: string;
  full_text: string;
}

interface AspectGroup {
  id: string;
  name: string;
  aspects: string[];
}

const getSentiment = (score: number): 'positive' | 'neutral' | 'negative' => {
  if (score > 0.3) return 'positive';
  if (score < -0.3) return 'negative';
  return 'neutral';
};

export default function ResultsPage() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState<{
    aspects: AspectData[];
    reviews: ReviewData[];
    total_reviews: number;
    status: string;
  } | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [aspectGroups, setAspectGroups] = useState<AspectGroup[]>([]);

  const [selectedAspectFilters, setSelectedAspectFilters] = useState<string[]>([]);
  const [selectedSentimentFilters, setSelectedSentimentFilters] = useState<string[]>([]);
  const [isAspectFilterOpen, setIsAspectFilterOpen] = useState(false);
  const [isSentimentFilterOpen, setIsSentimentFilterOpen] = useState(false);
  const [aspectFilterPosition, setAspectFilterPosition] = useState({ top: 0, left: 0 });
  const [sentimentFilterPosition, setSentimentFilterPosition] = useState({ top: 0, left: 0 });

  const [selectedAspectNames, setSelectedAspectNames] = useState<string[]>([]);
  const [selectedAspectSentiments, setSelectedAspectSentiments] = useState<string[]>([]);
  const [sortByFrequency, setSortByFrequency] = useState<'asc' | 'desc' | null>(null);
  const [sortByScore, setSortByScore] = useState<'asc' | 'desc' | null>(null);
  const [isAspectNameFilterOpen, setIsAspectNameFilterOpen] = useState(false);
  const [isAspectSentimentFilterOpen, setIsAspectSentimentFilterOpen] = useState(false);
  const [aspectNameFilterPosition, setAspectNameFilterPosition] = useState({ top: 0, left: 0 });
  const [aspectSentimentFilterPosition, setAspectSentimentFilterPosition] = useState({ top: 0, left: 0 });

  // Проверка наличия токена и существования сессии в localStorage
  useEffect(() => {
    if (!sessionId || !token) {
      navigate('/');
      return;
    }
    const sessions = JSON.parse(localStorage.getItem('my_sessions') || '[]');
    const sessionExists = sessions.some((s: any) => s.id === parseInt(sessionId));
    if (!sessionExists) {
      navigate('/');
    }
  }, [sessionId, token, navigate]);

  // Загрузка данных с передачей токена
  useEffect(() => {
    if (!sessionId || !token) return;
    apiGet(`/results/${sessionId}/data?skip=0&limit=50`, token)
      .then(res => {
        const aspects = res.aspects.map((a: any) => ({
          ...a,
          sentiment: getSentiment(a.sentiment_score),
        }));
        setData({ ...res, aspects });
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [sessionId, token]);

  const allReviewAspects = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>();
    data.reviews.forEach(r => {
      r.topics.split(',').map(t => t.trim()).filter(Boolean).forEach(t => {
        const match = t.match(/^(.+?)\(.+\)$/);
        if (match) set.add(match[1].trim());
      });
    });
    return Array.from(set);
  }, [data]);

  const sentimentOptions = [
    { value: 'positive', label: 'Позитивные' },
    { value: 'neutral', label: 'Нейтральные' },
    { value: 'negative', label: 'Негативные' },
  ];

  const handleDeepAnalysis = (aspect: string, isGroup?: boolean) => {
    if (isGroup) {
      const group = aspectGroups.find(g => g.name === aspect);
      if (group) {
        const aspectsParam = group.aspects.map(encodeURIComponent).join(',');
        navigate(`/deep/${sessionId}/${encodeURIComponent(aspect)}?aspects=${aspectsParam}&token=${encodeURIComponent(token!)}`);
        return;
      }
    }
    navigate(`/deep/${sessionId}/${encodeURIComponent(aspect)}?token=${encodeURIComponent(token!)}`);
  };

  const handleExportExcel = () => {
    import('xlsx').then(XLSX => {
      const aspectData = displayedAspects.map(a => ({
        'Аспект': a.name,
        'Всего упоминаний': a.total,
        'Позитивные': a.positive_count ?? 0,
        'Нейтральные': a.neutral_count ?? 0,
        'Негативные': a.negative_count ?? 0,
        'Оценка': a.sentiment_score.toFixed(2),
      }));

      const reviewData = filteredReviews.map((r, i) => ({
        '№': i + 1,
        'Текст отзыва': r.text,
        'Аспекты': r.aspectsList?.map(a => `${a.name}(${a.sentiment})`).join(', ') || r.topics,
        'Тональность': r.sentiment === 'positive' ? 'Позитивная' : r.sentiment === 'negative' ? 'Негативная' : 'Нейтральная',
      }));

      const wsAspects = XLSX.utils.json_to_sheet(aspectData);
      const wsReviews = XLSX.utils.json_to_sheet(reviewData);

      wsAspects['!cols'] = [{ wch: 25 }, { wch: 18 }, { wch: 12 }, { wch: 12 }, { wch: 12 }, { wch: 10 }];
      wsReviews['!cols'] = [{ wch: 5 }, { wch: 60 }, { wch: 40 }, { wch: 15 }];

      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, wsAspects, 'Аспекты');
      XLSX.utils.book_append_sheet(wb, wsReviews, 'Отзывы');

      XLSX.writeFile(wb, `analysis_${sessionId}.xlsx`);
    });
  };

  const handleCreateGroup = (name: string, aspectNames: string[]) => {
    const newGroup: AspectGroup = {
      id: Math.random().toString(36).substring(2, 15),
      name,
      aspects: aspectNames,
    };
    setAspectGroups([...aspectGroups, newGroup]);
  };

  const handleDeleteGroup = (groupId: string) => {
    setAspectGroups(aspectGroups.filter(g => g.id !== groupId));
  };

  const filteredReviews = useMemo(() => {
    if (!data) return [];
    let filtered = data.reviews.map(r => {
      const aspectsList = r.topics.split(',').map(t => {
        const match = t.trim().match(/^(.+?)\((.+)\)$/);
        return match ? { name: match[1].trim(), sentiment: match[2].trim() } : null;
      }).filter(Boolean) as { name: string; sentiment: string }[];
      const pos = aspectsList.filter(a => a.sentiment === 'positive').length;
      const neg = aspectsList.filter(a => a.sentiment === 'negative').length;
      let overallSentiment = 'neutral';
      if (pos > neg) overallSentiment = 'positive';
      else if (neg > pos) overallSentiment = 'negative';
      return { ...r, aspectsList, sentiment: overallSentiment };
    });

    if (selectedAspectFilters.length > 0) {
      filtered = filtered.filter(r => r.aspectsList.some(a => selectedAspectFilters.includes(a.name)));
    }
    if (selectedSentimentFilters.length > 0) {
      filtered = filtered.filter(r => selectedSentimentFilters.includes(r.sentiment));
    }
    return filtered;
  }, [data, selectedAspectFilters, selectedSentimentFilters]);

  const displayedAspects = useMemo(() => {
    if (!data) return [];
    const groupedNames = new Set(aspectGroups.flatMap(g => g.aspects));
    const individualAspects = data.aspects.filter(a => !groupedNames.has(a.name));
    const aggregatedGroups = aspectGroups.map(group => {
      const groupAspects = data.aspects.filter(a => group.aspects.includes(a.name));
      const totalCount = groupAspects.reduce((sum, a) => sum + a.total, 0);
      const posCount = groupAspects.reduce((sum, a) => sum + (a.positive_count || 0), 0);
      const neutCount = groupAspects.reduce((sum, a) => sum + (a.neutral_count || 0), 0);
      const negCount = groupAspects.reduce((sum, a) => sum + (a.negative_count || 0), 0);
      const avgScore = groupAspects.length
        ? groupAspects.reduce((sum, a) => sum + (a.average_score || 0), 0) / groupAspects.length
        : 0;
      const avgSentimentScore = groupAspects.length
        ? groupAspects.reduce((sum, a) => sum + a.sentiment_score, 0) / groupAspects.length
        : 0;
      return {
        name: group.name,
        total: totalCount,
        positivity: 0,
        negativity: 0,
        positive_count: posCount,
        neutral_count: neutCount,
        negative_count: negCount,
        sentiment_score: avgSentimentScore,
        average_score: parseFloat(avgScore.toFixed(1)),
        sentiment: getSentiment(avgSentimentScore),
        isGroup: true as const,
        groupId: group.id,
      };
    });

    let combined = [...individualAspects.map(a => ({ ...a, isGroup: false })), ...aggregatedGroups];

    if (selectedAspectNames.length > 0)
      combined = combined.filter(a => selectedAspectNames.includes(a.name));
    if (selectedAspectSentiments.length > 0)
      combined = combined.filter(a => selectedAspectSentiments.includes(a.sentiment));

    if (sortByFrequency)
      combined.sort((a, b) => sortByFrequency === 'asc' ? a.total - b.total : b.total - a.total);
    else if (sortByScore)
      combined.sort((a, b) => sortByScore === 'asc' ? a.sentiment_score - b.sentiment_score : b.sentiment_score - a.sentiment_score);

    return combined;
  }, [data, aspectGroups, selectedAspectNames, selectedAspectSentiments, sortByFrequency, sortByScore]);

  const { positivePercent, negativePercent } = useMemo(() => {
    if (!data) return { positivePercent: 0, negativePercent: 0 };
    const reviews = data.reviews.map(r => {
      const aspects = r.topics.split(',').map(t => {
        const match = t.trim().match(/^(.+?)\((.+)\)$/);
        return match ? match[2].trim() : null;
      }).filter(Boolean);
      const pos = aspects.filter(s => s === 'positive').length;
      const neg = aspects.filter(s => s === 'negative').length;
      return pos > neg ? 'positive' : neg > pos ? 'negative' : 'neutral';
    });
    const total = reviews.length;
    const positive = reviews.filter(r => r === 'positive').length;
    const negative = reviews.filter(r => r === 'negative').length;
    return {
      positivePercent: Math.round((positive / total) * 100),
      negativePercent: Math.round((negative / total) * 100),
    };
  }, [data]);

  const handleToggleAspectFilter = (aspectName: string) => {
    setSelectedAspectFilters(prev => prev.includes(aspectName) ? prev.filter(a => a !== aspectName) : [...prev, aspectName]);
  };

  const handleToggleSentimentFilter = (sentiment: string) => {
    setSelectedSentimentFilters(prev => prev.includes(sentiment) ? prev.filter(s => s !== sentiment) : [...prev, sentiment]);
  };

  const handleToggleAspectName = (name: string) => {
    setSelectedAspectNames(prev => prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]);
  };

  const handleToggleAspectSentiment = (sentiment: string) => {
    setSelectedAspectSentiments(prev => prev.includes(sentiment) ? prev.filter(s => s !== sentiment) : [...prev, sentiment]);
  };

  const handleSortFrequency = () => {
    setSortByFrequency(prev => prev === null ? 'desc' : prev === 'desc' ? 'asc' : null);
    setSortByScore(null);
  };

  const handleSortScore = () => {
    setSortByScore(prev => prev === null ? 'desc' : prev === 'desc' ? 'asc' : null);
    setSortByFrequency(null);
  };

  if (loading)
    return (
      <div className="min-h-screen bg-zinc-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400" />
      </div>
    );

  if (error)
    return (
      <div className="min-h-screen bg-zinc-50 flex items-center justify-center">
        <p className="text-red-500">Ошибка: {error}</p>
      </div>
    );

  if (!data) return null;

  return (
    <div className="min-h-screen bg-zinc-50">
      <div className="border-b border-zinc-300 bg-white">
        <div className="max-w-7xl mx-auto px-8 py-6">
          <button onClick={() => navigate('/')} className="flex items-center gap-2 text-sm text-zinc-600 hover:text-zinc-900 mb-4">
            <ArrowLeft className="w-4 h-4" /> Назад к загрузке
          </button>
          <h1 className="text-2xl font-medium text-zinc-900">Быстрый анализ</h1>
          <p className="text-sm text-zinc-600 mt-1">Сессия: {sessionId}</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-8 py-8">
        <div className="grid grid-cols-3 gap-6 mb-8">
          <div className="bg-white border border-zinc-300 rounded p-6">
            <div className="text-sm text-zinc-600 mb-1">Всего отзывов</div>
            <div className="text-3xl font-medium text-zinc-900">{data.total_reviews}</div>
          </div>
          <div className="bg-white border border-zinc-300 rounded p-6">
            <div className="text-sm text-zinc-600 mb-1 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-green-600" /> Позитивные
            </div>
            <div className="text-3xl font-medium text-green-600">{positivePercent}%</div>
          </div>
          <div className="bg-white border border-zinc-300 rounded p-6">
            <div className="text-sm text-zinc-600 mb-1 flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-red-600" /> Негативные
            </div>
            <div className="text-3xl font-medium text-red-600">{negativePercent}%</div>
          </div>
        </div>

        <div className="bg-white border border-zinc-300 rounded mb-8">
          <div className="border-b border-zinc-300 px-6 py-4">
            <h2 className="text-base font-medium text-zinc-900">Визуализация</h2>
          </div>
          <div className="p-6">
            <AspectChart
              aspects={displayedAspects.map(a => ({
                name: a.name,
                count: a.total,
                isGroup: a.isGroup,
                positiveCount: a.positive_count ?? 0,
                neutralCount: a.neutral_count ?? 0,
                negativeCount: a.negative_count ?? 0,
              }))}
              groups={aspectGroups}
            />
          </div>
        </div>

        <div className="bg-white border border-zinc-300 rounded mb-8">
          <div className="border-b border-zinc-300 px-6 py-4 flex items-center justify-between">
            <h2 className="text-base font-medium text-zinc-900">Аспекты</h2>
            <button onClick={() => setIsModalOpen(true)} className="flex items-center gap-2 px-4 py-2 border border-zinc-300 rounded text-sm text-zinc-900 hover:bg-zinc-50">
              <Settings2 className="w-4 h-4" /> Управление группами
            </button>
          </div>
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="w-full">
              <thead className="bg-zinc-50 border-b border-zinc-300 sticky top-0">
                <tr>
                  <th className="px-6 py-3 text-left">
                    <div className="relative inline-block">
                      <button onClick={(e) => { const rect = e.currentTarget.getBoundingClientRect(); setAspectNameFilterPosition({ top: rect.bottom, left: rect.left }); setIsAspectNameFilterOpen(!isAspectNameFilterOpen); }} className="flex items-center gap-1 text-xs font-medium text-zinc-600 uppercase hover:text-zinc-900">
                        Название <ChevronDown className={`w-3 h-3 ${isAspectNameFilterOpen ? 'rotate-180' : ''}`} />
                        {selectedAspectNames.length > 0 && <span className="ml-1 px-1.5 py-0.5 bg-zinc-900 text-white rounded text-xs">{selectedAspectNames.length}</span>}
                      </button>
                      {isAspectNameFilterOpen && (
                        <>
                          <div className="fixed inset-0 z-[90]" onClick={() => setIsAspectNameFilterOpen(false)} />
                          <div className="fixed w-64 bg-white border border-zinc-300 rounded shadow-lg z-[100] max-h-80 overflow-y-auto" style={{ top: aspectNameFilterPosition.top, left: aspectNameFilterPosition.left }}>
                            {[...data.aspects.map(a => a.name), ...aspectGroups.map(g => g.name)].map(name => (
                              <label key={name} className="flex items-center px-4 py-2 hover:bg-zinc-50 cursor-pointer border-b border-zinc-200 last:border-0">
                                <input type="checkbox" checked={selectedAspectNames.includes(name)} onChange={() => handleToggleAspectName(name)} className="w-4 h-4 border-zinc-300 rounded text-zinc-900" />
                                <span className="ml-2 text-sm text-zinc-900">{name}</span>
                              </label>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </th>
                  <th className="px-6 py-3 text-left">
                    <button onClick={handleSortFrequency} className="flex items-center gap-1 text-xs font-medium text-zinc-600 uppercase hover:text-zinc-900">
                      Частота <ArrowUpDown className="w-3 h-3" /> {sortByFrequency && <span className="text-zinc-900">{sortByFrequency === 'asc' ? '↑' : '↓'}</span>}
                    </button>
                  </th>
                  <th className="px-6 py-3 text-left">
                    <button onClick={handleSortScore} className="flex items-center gap-1 text-xs font-medium text-zinc-600 uppercase hover:text-zinc-900">
                      Оценка <ArrowUpDown className="w-3 h-3" /> {sortByScore && <span className="text-zinc-900">{sortByScore === 'asc' ? '↑' : '↓'}</span>}
                    </button>
                  </th>
                  <th className="px-6 py-3 text-left">
                    <div className="relative inline-block">
                      <button onClick={(e) => { const rect = e.currentTarget.getBoundingClientRect(); setAspectSentimentFilterPosition({ top: rect.bottom, left: rect.left }); setIsAspectSentimentFilterOpen(!isAspectSentimentFilterOpen); }} className="flex items-center gap-1 text-xs font-medium text-zinc-600 uppercase hover:text-zinc-900">
                        Тональность <ChevronDown className={`w-3 h-3 ${isAspectSentimentFilterOpen ? 'rotate-180' : ''}`} />
                        {selectedAspectSentiments.length > 0 && <span className="ml-1 px-1.5 py-0.5 bg-zinc-900 text-white rounded text-xs">{selectedAspectSentiments.length}</span>}
                      </button>
                      {isAspectSentimentFilterOpen && (
                        <>
                          <div className="fixed inset-0 z-[90]" onClick={() => setIsAspectSentimentFilterOpen(false)} />
                          <div className="fixed w-48 bg-white border border-zinc-300 rounded shadow-lg z-[100] max-h-80 overflow-y-auto" style={{ top: aspectSentimentFilterPosition.top, left: aspectSentimentFilterPosition.left }}>
                            {sentimentOptions.map(option => (
                              <label key={option.value} className="flex items-center px-4 py-2 hover:bg-zinc-50 cursor-pointer border-b border-zinc-200 last:border-0">
                                <input type="checkbox" checked={selectedAspectSentiments.includes(option.value)} onChange={() => handleToggleAspectSentiment(option.value)} className="w-4 h-4 border-zinc-300 rounded text-zinc-900" />
                                <span className="ml-2 text-sm text-zinc-900">{option.label}</span>
                              </label>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-zinc-600 uppercase">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200">
                {displayedAspects.map((aspect, idx) => (
                  <tr key={idx} className="hover:bg-zinc-50">
                    <td className="px-6 py-4 text-sm text-zinc-900">{'isGroup' in aspect && aspect.isGroup && '📁 '}{aspect.name}</td>
                    <td className="px-6 py-4 text-sm text-zinc-900">{aspect.total}</td>
                    <td className="px-6 py-4 text-sm text-zinc-900">{aspect.average_score.toFixed(1)}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                        aspect.sentiment === 'positive' ? 'bg-green-100 text-green-700' :
                        aspect.sentiment === 'negative' ? 'bg-red-100 text-red-700' : 'bg-zinc-100 text-zinc-700'
                      }`}>
                        {aspect.sentiment === 'positive' && <TrendingUp className="w-3 h-3" />}
                        {aspect.sentiment === 'negative' && <TrendingDown className="w-3 h-3" />}
                        {aspect.sentiment === 'neutral' && <AlertCircle className="w-3 h-3" />}
                        {aspect.sentiment === 'positive' ? 'Позитивный' : aspect.sentiment === 'negative' ? 'Негативный' : 'Нейтральный'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button onClick={() => handleDeepAnalysis(aspect.name, 'isGroup' in aspect && aspect.isGroup)} className="text-sm text-zinc-900 hover:text-zinc-600 font-medium">
                        Глубокий анализ →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-white border border-zinc-300 rounded">
          <div className="border-b border-zinc-300 px-6 py-4 flex items-center justify-between">
            <h2 className="text-base font-medium text-zinc-900">Детальная таблица отзывов</h2>
            <button onClick={handleExportExcel} className="flex items-center gap-2 px-4 py-2 border border-zinc-300 rounded text-sm text-zinc-900 hover:bg-zinc-50">
              <Download className="w-4 h-4" />
              Экспорт в Excel
            </button>
          </div>
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="w-full">
              <thead className="bg-zinc-50 border-b border-zinc-300 sticky top-0">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-600 uppercase">№</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-zinc-600 uppercase">Текст отзыва</th>
                  <th className="px-6 py-3 text-left">
                    <div className="relative inline-block">
                      <button onClick={(e) => { const rect = e.currentTarget.getBoundingClientRect(); setAspectFilterPosition({ top: rect.bottom, left: rect.left }); setIsAspectFilterOpen(!isAspectFilterOpen); }} className="flex items-center gap-1 text-xs font-medium text-zinc-600 uppercase hover:text-zinc-900">
                        Аспекты <ChevronDown className={`w-3 h-3 ${isAspectFilterOpen ? 'rotate-180' : ''}`} />
                        {selectedAspectFilters.length > 0 && <span className="ml-1 px-1.5 py-0.5 bg-zinc-900 text-white rounded text-xs">{selectedAspectFilters.length}</span>}
                      </button>
                      {isAspectFilterOpen && (
                        <>
                          <div className="fixed inset-0 z-[90]" onClick={() => setIsAspectFilterOpen(false)} />
                          <div className="fixed w-56 bg-white border border-zinc-300 rounded shadow-lg z-[100] max-h-80 overflow-y-auto" style={{ top: aspectFilterPosition.top, left: aspectFilterPosition.left }}>
                            {allReviewAspects.map(aspect => (
                              <label key={aspect} className="flex items-center px-4 py-2 hover:bg-zinc-50 cursor-pointer border-b border-zinc-200 last:border-0">
                                <input type="checkbox" checked={selectedAspectFilters.includes(aspect)} onChange={() => handleToggleAspectFilter(aspect)} className="w-4 h-4 border-zinc-300 rounded text-zinc-900" />
                                <span className="ml-2 text-sm text-zinc-900">{aspect}</span>
                              </label>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </th>
                  <th className="px-6 py-3 text-left">
                    <div className="relative inline-block">
                      <button onClick={(e) => { const rect = e.currentTarget.getBoundingClientRect(); setSentimentFilterPosition({ top: rect.bottom, left: rect.left }); setIsSentimentFilterOpen(!isSentimentFilterOpen); }} className="flex items-center gap-1 text-xs font-medium text-zinc-600 uppercase hover:text-zinc-900">
                        Тональность <ChevronDown className={`w-3 h-3 ${isSentimentFilterOpen ? 'rotate-180' : ''}`} />
                        {selectedSentimentFilters.length > 0 && <span className="ml-1 px-1.5 py-0.5 bg-zinc-900 text-white rounded text-xs">{selectedSentimentFilters.length}</span>}
                      </button>
                      {isSentimentFilterOpen && (
                        <>
                          <div className="fixed inset-0 z-[90]" onClick={() => setIsSentimentFilterOpen(false)} />
                          <div className="fixed w-48 bg-white border border-zinc-300 rounded shadow-lg z-[100] max-h-80 overflow-y-auto" style={{ top: sentimentFilterPosition.top, left: sentimentFilterPosition.left }}>
                            {sentimentOptions.map(option => (
                              <label key={option.value} className="flex items-center px-4 py-2 hover:bg-zinc-50 cursor-pointer border-b border-zinc-200 last:border-0">
                                <input type="checkbox" checked={selectedSentimentFilters.includes(option.value)} onChange={() => handleToggleSentimentFilter(option.value)} className="w-4 h-4 border-zinc-300 rounded text-zinc-900" />
                                <span className="ml-2 text-sm text-zinc-900">{option.label}</span>
                              </label>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200">
                {filteredReviews.map(review => (
                  <tr key={review.id} className="hover:bg-zinc-50">
                    <td className="px-6 py-4 text-sm text-zinc-500">{review.id}</td>
                    <td className="px-6 py-4 text-sm text-zinc-900 max-w-md">{review.text}</td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {review.aspectsList.map((a, i) => (
                          <span key={i} className="px-2 py-1 bg-zinc-100 text-zinc-700 text-xs rounded">{a.name}</span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-block w-2 h-2 rounded-full ${
                        review.sentiment === 'positive' ? 'bg-green-600' : review.sentiment === 'negative' ? 'bg-red-600' : 'bg-zinc-400'
                      }`} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <MergeAspectModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        aspects={data.aspects.map(a => ({ name: a.name, count: a.total }))}
        groups={aspectGroups}
        onCreateGroup={handleCreateGroup}
        onDeleteGroup={handleDeleteGroup}
      />
    </div>
  );
}