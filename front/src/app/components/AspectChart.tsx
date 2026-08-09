import { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ChevronDown } from 'lucide-react';

interface Aspect {
  name: string;
  count: number;
  isGroup?: boolean;
  positiveCount?: number;
  neutralCount?: number;
  negativeCount?: number;
}

interface AspectGroup {
  id: string;
  name: string;
  aspects: string[];
}

interface AspectChartProps {
  aspects: Aspect[];
  groups: AspectGroup[];
}

export default function AspectChart({ aspects, groups }: AspectChartProps) {
  const allOptions = [
    ...aspects.map((a) => ({ id: a.name, name: a.name, isGroup: false })),
    ...groups.map((g) => ({ id: g.id, name: g.name, isGroup: true })),
  ];

  const [selectedAspects, setSelectedAspects] = useState<string[]>(
    allOptions.slice(0, 5).map((a) => a.id)
  );
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const handleToggleAspect = (aspectId: string) => {
    setSelectedAspects((prev) =>
      prev.includes(aspectId)
        ? prev.filter((id) => id !== aspectId)
        : [...prev, aspectId]
    );
  };

  const chartData = selectedAspects
    .map((id) => {
      const aspect = aspects.find((a) => a.name === id);
      const group = groups.find((g) => g.id === id);
      if (!aspect && !group) return null;

      const name = aspect ? aspect.name : group!.name;
      const p = aspect?.positiveCount ?? 0;
      const n = aspect?.neutralCount ?? 0;
      const ng = aspect?.negativeCount ?? 0;

      return {
        id,
        name: name.length > 15 ? name.substring(0, 15) + '...' : name,
        fullName: name,
        Позитивные: p,
        Нейтральные: n,
        Негативные: ng,
      };
    })
    .filter((item): item is NonNullable<typeof item> => item !== null);

  return (
    <div>
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-600 uppercase">Выберите аспекты:</span>
          <div className="relative">
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center gap-2 px-4 py-2 border border-zinc-300 rounded text-sm text-zinc-900 hover:bg-zinc-50"
            >
              <span>Выбрано: {selectedAspects.length}</span>
              <ChevronDown className={`w-4 h-4 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {isDropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setIsDropdownOpen(false)}
                />
                <div className="absolute top-full left-0 mt-1 w-64 bg-white border border-zinc-300 rounded shadow-lg z-20 max-h-80 overflow-y-auto">
                  {aspects.length > 0 && (
                    <>
                      <div className="px-4 py-2 bg-zinc-50 border-b border-zinc-200">
                        <span className="text-xs font-medium text-zinc-600 uppercase">Аспекты</span>
                      </div>
                      {aspects.map((aspect) => (
                        <label
                          key={aspect.name}
                          className="flex items-center px-4 py-2 hover:bg-zinc-50 cursor-pointer border-b border-zinc-200"
                        >
                          <input
                            type="checkbox"
                            checked={selectedAspects.includes(aspect.name)}
                            onChange={() => handleToggleAspect(aspect.name)}
                            className="w-4 h-4 border-zinc-300 rounded text-zinc-900"
                          />
                          <span className="ml-2 text-sm text-zinc-900">{aspect.name}</span>
                        </label>
                      ))}
                    </>
                  )}

                  {groups.length > 0 && (
                    <>
                      <div className="px-4 py-2 bg-zinc-50 border-b border-zinc-200">
                        <span className="text-xs font-medium text-zinc-600 uppercase">Группы</span>
                      </div>
                      {groups.map((group) => (
                        <label
                          key={group.id}
                          className="flex items-center px-4 py-2 hover:bg-zinc-50 cursor-pointer border-b border-zinc-200 last:border-0"
                        >
                          <input
                            type="checkbox"
                            checked={selectedAspects.includes(group.id)}
                            onChange={() => handleToggleAspect(group.id)}
                            className="w-4 h-4 border-zinc-300 rounded text-zinc-900"
                          />
                          <span className="ml-2 text-sm text-zinc-900">📁 {group.name}</span>
                        </label>
                      ))}
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
            <XAxis
              dataKey="name"
              angle={-45}
              textAnchor="end"
              height={80}
              tick={{ fill: '#52525b', fontSize: 12 }}
            />
            <YAxis tick={{ fill: '#52525b', fontSize: 12 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #d4d4d8',
                borderRadius: '4px',
              }}
              labelFormatter={(label) => {
                const item = chartData.find((d) => d?.name === label);
                return item?.fullName || label;
              }}
            />
            <Legend
              wrapperStyle={{ paddingTop: '20px' }}
              iconType="rect"
            />
            <Bar dataKey="Позитивные" fill="#16a34a" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Нейтральные" fill="#71717a" radius={[4, 4, 0, 0]} />
            <Bar dataKey="Негативные" fill="#dc2626" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-80 flex items-center justify-center border-2 border-dashed border-zinc-300 rounded">
          <p className="text-sm text-zinc-600">Выберите хотя бы один аспект для отображения</p>
        </div>
      )}
    </div>
  );
}